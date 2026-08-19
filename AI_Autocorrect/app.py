import html
import json
import os
import re
from difflib import SequenceMatcher
from functools import wraps
from io import BytesIO
from typing import Any, Dict, List

from flask import Flask, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from services.analytics_service import build_admin_dashboard
from services.transformer_service import get_transformer_corrector
from utils.auth import hash_password, is_valid_email, normalize_email, verify_password
from utils.database import (
    fetch_corrections,
    get_correction_by_id,
    get_dashboard_summary,
    get_user_by_email,
    get_user_by_id,
    initialize_database,
    list_users,
    save_correction,
    save_user,
)
from utils.grammar import (
    analyze_sentiment,
    calculate_readability,
    extract_keywords,
    correct_grammar,
)
from utils.spellchecker import normalize_language, analyze_spelling


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.environ.get("AUTOCORRECT_DATABASE_PATH", os.path.join(BASE_DIR, "database.db"))
SUPPORTED_LANGUAGES = [
    {"code": "en", "label": "English"},
    {"code": "es", "label": "Spanish"},
    {"code": "fr", "label": "French"},
    {"code": "de", "label": "German"},
    {"code": "pt", "label": "Portuguese"},
    {"code": "it", "label": "Italian"},
    {"code": "nl", "label": "Dutch"},
]


app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "ai-autocorrect-tool"),
    DATABASE_PATH=DATABASE_PATH,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

initialize_database(DATABASE_PATH)
transformer_corrector = get_transformer_corrector()


@app.context_processor
def inject_user_context() -> Dict[str, Any]:
    current_user = g.get("current_user")
    return {
        "current_user": current_user,
        "is_authenticated": bool(current_user),
        "is_admin": bool(current_user and current_user.get("role") == "admin"),
    }


@app.before_request
def load_current_user() -> None:
    user_id = session.get("user_id")
    g.current_user = get_user_by_id(DATABASE_PATH, user_id) if user_id else None


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not g.get("current_user"):
            flash("Please sign in to access this area.", "warning")
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped_view


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        user = g.get("current_user")
        if not user:
            flash("Administrator access is required.", "warning")
            return redirect(url_for("login", next=request.path))
        if user.get("role") != "admin":
            flash("You do not have permission to access the admin dashboard.", "danger")
            return redirect(url_for("index"))
        return view_func(*args, **kwargs)

    return wrapped_view


def process_text(
    text: str,
    language: str = "en",
    context_before: str = ""
) -> Dict[str, Any]:

    cleaned_text = (text or "").strip()
    normalized_language = normalize_language(language)

    if not cleaned_text:
        return {
            "original_text": "",
            "corrected_text": "",
            "language": normalized_language,
            "analysis_mode": "none",
            "transformer_model": "",
            "transformer_used": False,
            "context_before": context_before,
            "corrections": [],
            "explanations": [],
            "keywords": [],
            "stats": {
                "total_words": 0,
                "incorrect_words_found": 0,
                "corrections_applied": 0,
                "accuracy_percentage": 100.0,
                "readability_score": 100.0,
                "confidence_score": 0.0,
            },
            "readability_score": 100.0,
            "sentiment_label": "Neutral",
            "sentiment_polarity": 0.0,
            "confidence_score": 0.0,
            "diff_html": build_diff_views("", ""),
            "message": "No text provided.",
        }

    # Try Claude first
    transformer_result = transformer_corrector.correct(
        cleaned_text,
        context_before=context_before,
        language=normalized_language,
    )

    corrections = []
    final_text = cleaned_text
    used_ai = transformer_result.used_transformer

    # ---------------------------------------------------------
    # CLAUDE SUCCESS
    # ---------------------------------------------------------
    if used_ai:

        final_text = (
            transformer_result.corrected_text
            or cleaned_text
        )

        for change in transformer_result.changes:

            original = change.get("original", "")
            corrected = change.get("corrected", "")

            if not original or not corrected:
                continue

            corrections.append({
                "type": "ai_correction",
                "original": original,
                "corrected": corrected,
                "reason": change.get(
                    "reason",
                    "Corrected by AI for spelling or grammar."
                ),
                "better_choice": change.get(
                    "reason",
                    "This correction improves grammatical correctness."
                ),
                "suggestions": [corrected],
                "confidence": (
                    transformer_result.confidence_score / 100
                ),
            })

        analysis_mode = "claude-ai"

        message = "Text corrected successfully using AI."

    # ---------------------------------------------------------
    # LOCAL FALLBACK
    # ---------------------------------------------------------
    else:

        spelling_result = analyze_spelling(
            cleaned_text,
            normalized_language
        )

        spelling_text = spelling_result["corrected_text"]

        grammar_result = correct_grammar(
            spelling_text,
            normalized_language
        )

        final_text = grammar_result["corrected_text"]

        # Spelling corrections
        for issue in spelling_result.get("issues", []):

            corrections.append({
                "type": "spelling",
                "original": issue.get("original"),
                "corrected": issue.get("corrected"),
                "reason": issue.get(
                    "reason",
                    "Possible spelling mistake."
                ),
                "better_choice": issue.get(
                    "better_choice",
                    "The suggested word is a closer dictionary match."
                ),
                "suggestions": issue.get(
                    "suggestions",
                    []
                ),
                "confidence": issue.get(
                    "confidence",
                    0.75
                ),
            })

        # Grammar corrections
        for issue in grammar_result.get("issues", []):

            corrections.append({
                "type": "grammar",
                "original": issue.get("original"),
                "corrected": issue.get("corrected"),
                "reason": issue.get(
                    "reason",
                    "Grammar or punctuation improvement."
                ),
                "better_choice": issue.get(
                    "better_choice",
                    "The corrected sentence follows standard English usage."
                ),
                "suggestions": issue.get(
                    "suggestions",
                    []
                ),
                "confidence": issue.get(
                    "confidence",
                    0.78
                ),
            })

        analysis_mode = "local-fallback"

        fallback_confidence = max(
            spelling_result.get("confidence", 1.0),
            grammar_result.get("confidence", 1.0),
        )

        transformer_result.confidence_score = round(
            fallback_confidence * 100,
            2
        )

        message = (
            "AI service unavailable. "
            "Local spelling and grammar correction was used."
        )

    # ---------------------------------------------------------
    # STATISTICS
    # ---------------------------------------------------------

    total_words = len(
        re.findall(r"\b[\w'-]+\b", cleaned_text)
    )

    incorrect_words = len(corrections)

    corrections_applied = sum(
        1
        for item in corrections
        if item.get("original") != item.get("corrected")
    )

    accuracy = (
        100.0
        if total_words == 0
        else round(
            max(
                0.0,
                ((total_words - incorrect_words) / total_words) * 100
            ),
            2,
        )
    )

    readability_score = calculate_readability(
        final_text
    )

    sentiment_result = analyze_sentiment(
        final_text
    )

    keywords = extract_keywords(
        final_text,
        normalized_language
    )

    confidence_score = round(
        transformer_result.confidence_score,
        2
    )

    # ---------------------------------------------------------
    # EXPLANATIONS
    # ---------------------------------------------------------

    explanations = []

    for item in corrections:

        confidence = float(
            item.get("confidence", 0)
        )

        if confidence <= 1:
            confidence *= 100

        explanations.append({
            "original": item.get("original"),
            "corrected": item.get("corrected"),
            "reason": item.get("reason"),
            "better_choice": item.get("better_choice"),
            "suggestions": item.get(
                "suggestions",
                []
            ),
            "confidence": round(
                confidence,
                2
            ),
            "type": item.get(
                "type",
                "correction"
            ),
        })

    diff_views = build_diff_views(
        cleaned_text,
        final_text
    )

    return {
        "original_text": cleaned_text,
        "corrected_text": final_text,
        "language": normalized_language,

        "analysis_mode": analysis_mode,
        "transformer_model": transformer_result.model_name,
        "transformer_used": used_ai,

        "context_before": context_before,

        "corrections": corrections,
        "explanations": explanations,

        "keywords": keywords,

        "stats": {
            "total_words": total_words,
            "incorrect_words_found": incorrect_words,
            "corrections_applied": corrections_applied,
            "accuracy_percentage": accuracy,
            "readability_score": readability_score,
            "confidence_score": confidence_score,
        },

        "readability_score": readability_score,

        "sentiment_label": sentiment_result["label"],
        "sentiment_polarity": sentiment_result["polarity"],

        "confidence_score": confidence_score,

        "diff_html": diff_views,

        "message": message,
    }


def build_diff_views(original_text: str, corrected_text: str) -> Dict[str, str]:
    original_tokens = tokenize_for_diff(original_text)
    corrected_tokens = tokenize_for_diff(corrected_text)
    matcher = SequenceMatcher(a=original_tokens, b=corrected_tokens)

    original_html: List[str] = []
    corrected_html: List[str] = []

    for tag, start_a, end_a, start_b, end_b in matcher.get_opcodes():
        original_chunk = escape_join(original_tokens[start_a:end_a])
        corrected_chunk = escape_join(corrected_tokens[start_b:end_b])

        if tag == "equal":
            original_html.append(original_chunk)
            corrected_html.append(corrected_chunk)
        elif tag == "delete":
            original_html.append(f'<span class="diff-del">{original_chunk}</span>')
        elif tag == "insert":
            corrected_html.append(f'<span class="diff-add">{corrected_chunk}</span>')
        elif tag == "replace":
            original_html.append(f'<span class="diff-del">{original_chunk}</span>')
            corrected_html.append(f'<span class="diff-add">{corrected_chunk}</span>')

    return {"original": "".join(original_html), "corrected": "".join(corrected_html)}


def tokenize_for_diff(text: str) -> List[str]:
    return re.findall(r"\s+|[\w'-]+|[^\w\s]", text or "", re.UNICODE)


def escape_join(tokens: List[str]) -> str:
    return "".join(html.escape(token) for token in tokens)


@app.route("/")
def index() -> str:
    recent_history = fetch_corrections(
        DATABASE_PATH,
        limit=6,
        user_id=g.current_user["id"] if g.get("current_user") else None,
        admin_view=bool(g.get("current_user") and g.current_user.get("role") == "admin"),
    )
    dashboard_totals = get_dashboard_summary(DATABASE_PATH)["totals"]
    return render_template("index.html", languages=SUPPORTED_LANGUAGES, recent_history=recent_history, dashboard_totals=dashboard_totals)


@app.route("/auth/register", methods=["GET", "POST"])
def register() -> str:
    if g.get("current_user"):
        return redirect(url_for("index"))

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        email = normalize_email(request.form.get("email") or "")
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not full_name or not email or not password:
            flash("Please fill in every field.", "danger")
        elif not is_valid_email(email):
            flash("Enter a valid email address.", "danger")
        elif len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        elif get_user_by_email(DATABASE_PATH, email):
            flash("An account with that email already exists.", "danger")
        else:
            user_id = save_user(DATABASE_PATH, full_name, email, hash_password(password))
            session["user_id"] = user_id
            flash("Account created successfully.", "success")
            return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/auth/login", methods=["GET", "POST"])
def login() -> str:
    if g.get("current_user"):
        return redirect(url_for("index"))

    if request.method == "POST":
        email = normalize_email(request.form.get("email") or "")
        password = request.form.get("password") or ""
        user = get_user_by_email(DATABASE_PATH, email)

        if user and verify_password(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash("Welcome back.", "success")
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/auth/logout")
def logout() -> str:
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


@app.route("/history")
@login_required
def history() -> str:
    query = request.args.get("q", "").strip()
    user = g.current_user
    corrections = fetch_corrections(
        DATABASE_PATH,
        search_query=query,
        limit=100,
        user_id=user["id"],
        admin_view=user.get("role") == "admin",
    )
    return render_template("history.html", corrections=corrections, query=query, languages=SUPPORTED_LANGUAGES)


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard() -> str:
    dashboard = build_admin_dashboard(DATABASE_PATH)
    users = list_users(DATABASE_PATH, limit=12)
    return render_template("admin.html", dashboard=dashboard, users=users)


@app.route("/api/preview", methods=["POST"])
def api_preview():
    payload = request.get_json(silent=True) or request.form.to_dict()
    text = (payload.get("text") or "").strip()
    language = payload.get("language", "en")
    context_before = payload.get("context_before", "")

    if not text:
        return jsonify({"success": False, "message": "Please enter text to analyze."}), 400

    result = process_text(text, language, context_before=context_before)
    result["success"] = True
    result["stored"] = False
    result["message"] = "Live typing suggestions updated."
    return jsonify(result)


@app.route("/api/suggest", methods=["POST"])
def api_suggest():
    payload = request.get_json(silent=True) or request.form.to_dict()
    text = (payload.get("text") or "").strip()
    language = payload.get("language", "en")
    context_before = payload.get("context_before", "")

    if not text:
        return jsonify({"success": False, "message": "Please enter text to generate suggestions."}), 400

    result = process_text(text, language, context_before=context_before)
    result["suggestions"] = result.get("corrections", [])[:5]
    result["success"] = True
    return jsonify(result)


@app.route("/api/correct", methods=["POST"])
def api_correct():
    payload = request.get_json(silent=True) or request.form.to_dict()
    text = (payload.get("text") or "").strip()
    language = payload.get("language", "en")
    context_before = payload.get("context_before", "")

    if not text:
        return jsonify({"success": False, "message": "Please enter text to correct."}), 400

    result = process_text(text, language, context_before=context_before)
    current_user = g.get("current_user")
    record_id = None
    if current_user:
        record_id = save_correction(DATABASE_PATH, result, user_id=current_user["id"])

    result["success"] = True
    result["stored"] = bool(record_id)
    result["history_id"] = record_id
    result["message"] = "Text corrected and saved to your history." if record_id else "Text corrected locally. Sign in to save history and exports."
    return jsonify(result)


@app.route("/api/history")
@login_required
def api_history():
    query = request.args.get("q", "").strip()
    user = g.current_user
    corrections = fetch_corrections(
        DATABASE_PATH,
        search_query=query,
        limit=100,
        user_id=user["id"],
        admin_view=user.get("role") == "admin",
    )
    return jsonify({"success": True, "items": corrections})


@app.route("/api/history/<int:correction_id>")
@login_required
def api_history_detail(correction_id: int):
    correction = get_correction_by_id(DATABASE_PATH, correction_id)
    if not correction:
        return jsonify({"success": False, "message": "Correction not found."}), 404

    user = g.current_user
    if user.get("role") != "admin" and correction.get("user_id") not in {None, user["id"]}:
        return jsonify({"success": False, "message": "Not authorized to view this correction."}), 403

    return jsonify({"success": True, "item": correction})


@app.route("/export/txt/<int:correction_id>")
@login_required
def export_txt(correction_id: int):
    correction = get_correction_by_id(DATABASE_PATH, correction_id)
    if not correction:
        return jsonify({"success": False, "message": "Correction not found."}), 404

    user = g.current_user
    if user.get("role") != "admin" and correction.get("user_id") not in {None, user["id"]}:
        return jsonify({"success": False, "message": "Not authorized to export this correction."}), 403

    content = [
        "AI-Powered Autocorrect Tool",
        f"Record ID: {correction['id']}",
        f"Language: {correction['language']}",
        f"Analysis Mode: {correction.get('analysis_mode', 'rules-only')}",
        f"Transformer Model: {correction.get('transformer_model', 'n/a')}",
        "",
        "Original Text:",
        correction["original_text"],
        "",
        "Corrected Text:",
        correction["corrected_text"],
        "",
        "Statistics:",
        json.dumps(correction.get("stats", {}), indent=2),
        "",
        "Explanations:",
        json.dumps(correction.get("explanations", []), indent=2),
    ]
    buffer = BytesIO("\n".join(content).encode("utf-8"))
    return send_file(buffer, as_attachment=True, download_name=f"autocorrect_{correction_id}.txt", mimetype="text/plain")


@app.route("/export/pdf/<int:correction_id>")
@login_required
def export_pdf(correction_id: int):
    correction = get_correction_by_id(DATABASE_PATH, correction_id)
    if not correction:
        return jsonify({"success": False, "message": "Correction not found."}), 404

    user = g.current_user
    if user.get("role") != "admin" and correction.get("user_id") not in {None, user["id"]}:
        return jsonify({"success": False, "message": "Not authorized to export this correction."}), 403

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    left_margin = 50
    right_margin = 50
    max_width = width - left_margin - right_margin
    y = height - 50

    def draw_wrapped_lines(title: str, body: str) -> None:
        nonlocal y
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(left_margin, y, title)
        y -= 16
        pdf.setFont("Helvetica", 10)
        for line in simpleSplit(body, "Helvetica", 10, max_width):
            if y < 70:
                pdf.showPage()
                y = height - 50
                pdf.setFont("Helvetica", 10)
            pdf.drawString(left_margin, y, line)
            y -= 14
        y -= 8

    pdf.setTitle(f"AI Autocorrect Report {correction_id}")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left_margin, y, "AI-Powered Autocorrect Tool")
    y -= 24
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        left_margin,
        y,
        f"Record ID: {correction['id']} | Language: {correction['language']} | Confidence: {correction.get('confidence_score', 0)}",
    )
    y -= 24

    draw_wrapped_lines("Original Text", correction["original_text"])
    draw_wrapped_lines("Corrected Text", correction["corrected_text"])
    draw_wrapped_lines("Statistics", json.dumps(correction.get("stats", {}), indent=2))
    draw_wrapped_lines("Explanations", json.dumps(correction.get("explanations", []), indent=2))

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"autocorrect_{correction_id}.pdf", mimetype="application/pdf")


@app.route("/api/analytics")
@admin_required
def api_analytics():
    return jsonify({"success": True, "dashboard": build_admin_dashboard(DATABASE_PATH)})


@app.route("/health")
def health() -> Any:
    return jsonify({"success": True, "status": "healthy"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
