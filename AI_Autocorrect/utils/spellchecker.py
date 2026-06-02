import re
from typing import Any, Dict, List, Tuple

from spellchecker import SpellChecker


LANGUAGE_MAP = {
    "en": "en",
    "english": "en",
    "es": "es",
    "spanish": "es",
    "fr": "fr",
    "french": "fr",
    "de": "de",
    "german": "de",
    "pt": "pt",
    "portuguese": "pt",
    "it": "it",
    "italian": "it",
    "nl": "nl",
    "dutch": "nl",
}

SUPPORTED_SPELLCHECKER_LANGUAGES = ["en", "es", "fr", "de", "pt", "it", "nl"]

WORD_PATTERN = re.compile(r"\b[\w']+\b|\s+|[^\w\s]", re.UNICODE)


def normalize_language(language: str) -> str:
    return LANGUAGE_MAP.get((language or "en").strip().lower(), "en")


def _preserve_case(original: str, candidate: str) -> str:
    if original.isupper():
        return candidate.upper()
    if original.istitle():
        return candidate.title()
    if original[:1].isupper():
        return candidate[:1].upper() + candidate[1:]
    return candidate


def _candidate_suggestions(spell: SpellChecker, token: str) -> List[str]:
    suggestions = list(spell.candidates(token) or [])
    suggestions = sorted(suggestions, key=lambda value: (-len(value), value))
    ranked: List[str] = []
    if spell.correction(token):
        ranked.append(spell.correction(token))
    for suggestion in suggestions:
        if suggestion not in ranked:
            ranked.append(suggestion)
    return ranked[:3]


def analyze_spelling(text: str, language: str = "en") -> Dict[str, Any]:
    normalized_language = normalize_language(language)
    spell = SpellChecker(language=normalized_language)

    tokens = WORD_PATTERN.findall(text or "")
    issues: List[Dict[str, Any]] = []
    corrected_tokens: List[str] = []

    for token in tokens:
        if token.isspace() or not re.search(r"[A-Za-z]", token):
            corrected_tokens.append(token)
            continue

        bare_token = token.strip("'\"")
        if not bare_token or bare_token.lower() in spell:
            corrected_tokens.append(token)
            continue

        correction = spell.correction(bare_token.lower()) or bare_token
        suggestion_list = _candidate_suggestions(spell, bare_token.lower())
        suggestion_list = [_preserve_case(token, suggestion) for suggestion in suggestion_list]
        corrected_word = _preserve_case(token, correction)
        corrected_tokens.append(corrected_word)

        rank = suggestion_list.index(corrected_word) if corrected_word in suggestion_list else 2
        confidence = max(0.5, round(0.93 - (rank * 0.12), 2))

        issues.append(
            {
                "type": "spelling",
                "original": token,
                "corrected": corrected_word,
                "suggestions": suggestion_list,
                "reason": f"'{token}' is not found in the selected language dictionary.",
                "better_choice": f"'{corrected_word}' is the closest dictionary match and is more likely to be correct.",
                "confidence": confidence,
            }
        )

    corrected_text = "".join(corrected_tokens)
    return {
        "original_text": text or "",
        "corrected_text": corrected_text,
        "issues": issues,
        "confidence": round(_average_confidence(issues), 2),
        "issue_count": len(issues),
    }


def _average_confidence(issues: List[Dict[str, Any]]) -> float:
    if not issues:
        return 1.0
    return sum(issue.get("confidence", 0.0) for issue in issues) / len(issues)
