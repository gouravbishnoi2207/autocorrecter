import json
import os
import sqlite3
from collections import Counter
from typing import Any, Dict, List, Optional

from werkzeug.security import generate_password_hash


DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database.db")
DEFAULT_ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@ai-autocorrect.local")
DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@12345!")
DEFAULT_ADMIN_NAME = os.environ.get("ADMIN_NAME", "Platform Admin")


CORRECTION_COLUMNS = {
    "user_id": "INTEGER",
    "analysis_mode": "TEXT NOT NULL DEFAULT 'transformer'",
    "transformer_model": "TEXT NOT NULL DEFAULT 'prithivida/grammar_error_correcter_v1'",
    "context_before": "TEXT NOT NULL DEFAULT ''",
    "keywords_json": "TEXT NOT NULL DEFAULT '[]'",
}


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: str = DEFAULT_DB_PATH) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with get_connection(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                original_text TEXT NOT NULL,
                corrected_text TEXT NOT NULL,
                language TEXT NOT NULL,
                analysis_mode TEXT NOT NULL DEFAULT 'transformer',
                transformer_model TEXT NOT NULL DEFAULT 'prithivida/grammar_error_correcter_v1',
                context_before TEXT NOT NULL DEFAULT '',
                corrections_json TEXT NOT NULL,
                stats_json TEXT NOT NULL,
                explanations_json TEXT NOT NULL,
                keywords_json TEXT NOT NULL DEFAULT '[]',
                readability_score REAL NOT NULL DEFAULT 0,
                sentiment_label TEXT NOT NULL DEFAULT 'Neutral',
                confidence_score REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )

        _ensure_columns(connection, "corrections", CORRECTION_COLUMNS)
        _seed_admin_user(connection)
        connection.commit()


def _seed_admin_user(connection: sqlite3.Connection) -> None:
    existing = connection.execute("SELECT id FROM users WHERE email = ?", (DEFAULT_ADMIN_EMAIL,)).fetchone()
    if existing:
        return

    connection.execute(
        """
        INSERT INTO users (full_name, email, password_hash, role)
        VALUES (?, ?, ?, 'admin')
        """,
        (DEFAULT_ADMIN_NAME, DEFAULT_ADMIN_EMAIL, generate_password_hash(DEFAULT_ADMIN_PASSWORD)),
    )


def _ensure_columns(connection: sqlite3.Connection, table_name: str, columns: Dict[str, str]) -> None:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_columns = {row["name"] for row in rows}
    for column_name, column_definition in columns.items():
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def save_user(db_path: str, full_name: str, email: str, password_hash: str, role: str = "user") -> int:
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (full_name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            (full_name, email, password_hash, role),
        )
        connection.commit()
        return int(cursor.lastrowid)


def get_user_by_email(db_path: str, email: str) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as connection:
        row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return row_to_user(row) if row else None


def get_user_by_id(db_path: str, user_id: int) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as connection:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return row_to_user(row) if row else None


def list_users(db_path: str, limit: int = 100) -> List[Dict[str, Any]]:
    with get_connection(db_path) as connection:
        rows = connection.execute("SELECT * FROM users ORDER BY datetime(created_at) DESC LIMIT ?", (limit,)).fetchall()
    return [row_to_user(row) for row in rows]


def save_correction(db_path: str, payload: Dict[str, Any], user_id: Optional[int] = None) -> int:
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO corrections (
                user_id,
                original_text,
                corrected_text,
                language,
                analysis_mode,
                transformer_model,
                context_before,
                corrections_json,
                stats_json,
                explanations_json,
                keywords_json,
                readability_score,
                sentiment_label,
                confidence_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                payload["original_text"],
                payload["corrected_text"],
                payload["language"],
                payload.get("analysis_mode", "transformer"),
                payload.get("transformer_model", "prithivida/grammar_error_correcter_v1"),
                payload.get("context_before", ""),
                json.dumps(payload.get("corrections", []), ensure_ascii=False),
                json.dumps(payload.get("stats", {}), ensure_ascii=False),
                json.dumps(payload.get("explanations", []), ensure_ascii=False),
                json.dumps(payload.get("keywords", []), ensure_ascii=False),
                payload.get("readability_score", 0),
                payload.get("sentiment_label", "Neutral"),
                payload.get("confidence_score", 0),
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def fetch_corrections(
    db_path: str,
    search_query: str = "",
    limit: int = 100,
    user_id: Optional[int] = None,
    admin_view: bool = False,
) -> List[Dict[str, Any]]:
    sql = """
        SELECT corrections.*, users.full_name AS user_full_name, users.email AS user_email, users.role AS user_role
        FROM corrections
        LEFT JOIN users ON corrections.user_id = users.id
    """
    params: List[Any] = []
    conditions: List[str] = []

    if user_id is not None and not admin_view:
        conditions.append("(corrections.user_id = ? OR corrections.user_id IS NULL)")
        params.append(user_id)

    if search_query:
        like_query = f"%{search_query}%"
        conditions.append("(corrections.original_text LIKE ? OR corrections.corrected_text LIKE ? OR corrections.language LIKE ?)")
        params.extend([like_query, like_query, like_query])

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY datetime(corrections.created_at) DESC, corrections.id DESC LIMIT ?"
    params.append(limit)

    with get_connection(db_path) as connection:
        rows = connection.execute(sql, params).fetchall()

    return [row_to_correction(row) for row in rows]


def get_correction_by_id(db_path: str, correction_id: int) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT corrections.*, users.full_name AS user_full_name, users.email AS user_email, users.role AS user_role
            FROM corrections
            LEFT JOIN users ON corrections.user_id = users.id
            WHERE corrections.id = ?
            """,
            (correction_id,),
        ).fetchone()

    return row_to_correction(row) if row else None


def get_dashboard_summary(db_path: str) -> Dict[str, Any]:
    with get_connection(db_path) as connection:
        totals = connection.execute(
            """
            SELECT
                COUNT(*) AS total_corrections,
                AVG(confidence_score) AS avg_confidence,
                AVG(readability_score) AS avg_readability,
                SUM(CASE WHEN sentiment_label = 'Positive' THEN 1 ELSE 0 END) AS positive_count,
                SUM(CASE WHEN sentiment_label = 'Negative' THEN 1 ELSE 0 END) AS negative_count,
                SUM(CASE WHEN sentiment_label = 'Neutral' THEN 1 ELSE 0 END) AS neutral_count
            FROM corrections
            """
        ).fetchone()

        user_totals = connection.execute(
            """
            SELECT
                COUNT(*) AS total_users,
                SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) AS admin_users,
                SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS regular_users
            FROM users
            """
        ).fetchone()

        language_rows = connection.execute(
            "SELECT language, COUNT(*) AS total FROM corrections GROUP BY language ORDER BY total DESC, language ASC"
        ).fetchall()

        trend_rows = connection.execute(
            """
            SELECT date(created_at) AS day, COUNT(*) AS total, AVG(confidence_score) AS avg_confidence
            FROM corrections
            GROUP BY date(created_at)
            ORDER BY day DESC
            LIMIT 14
            """
        ).fetchall()

        model_rows = connection.execute(
            "SELECT analysis_mode, COUNT(*) AS total FROM corrections GROUP BY analysis_mode ORDER BY total DESC"
        ).fetchall()

        recent_rows = connection.execute(
            """
            SELECT corrections.id, corrections.original_text, corrections.corrected_text, corrections.language,
                   corrections.confidence_score, corrections.readability_score, corrections.created_at,
                   users.full_name AS user_full_name
            FROM corrections
            LEFT JOIN users ON corrections.user_id = users.id
            ORDER BY datetime(corrections.created_at) DESC, corrections.id DESC
            LIMIT 8
            """
        ).fetchall()

    language_distribution = [{"label": row["language"], "value": row["total"]} for row in language_rows]
    activity_trend = [
        {"label": row["day"], "value": row["total"], "confidence": round(row["avg_confidence"] or 0, 2)}
        for row in reversed(trend_rows)
    ]

    analysis_mode_distribution = [{"label": row["analysis_mode"], "value": row["total"]} for row in model_rows]
    # recent_rows selects a subset of columns; build lightweight correction dicts
    recent_corrections = []
    for row in recent_rows:
        recent_corrections.append(
            {
                "id": row["id"],
                "user_full_name": row["user_full_name"],
                "original_text": row["original_text"],
                "corrected_text": row["corrected_text"],
                "language": row["language"],
                "confidence_score": row["confidence_score"],
                "readability_score": row["readability_score"],
                "created_at": row["created_at"],
            }
        )

    return {
        "totals": {
            "total_corrections": totals["total_corrections"] if totals else 0,
            "avg_confidence": round(totals["avg_confidence"] or 0, 2) if totals else 0,
            "avg_readability": round(totals["avg_readability"] or 0, 2) if totals else 0,
            "positive_count": totals["positive_count"] if totals else 0,
            "negative_count": totals["negative_count"] if totals else 0,
            "neutral_count": totals["neutral_count"] if totals else 0,
            "total_users": user_totals["total_users"] if user_totals else 0,
            "admin_users": user_totals["admin_users"] if user_totals else 0,
            "regular_users": user_totals["regular_users"] if user_totals else 0,
        },
        "language_distribution": language_distribution,
        "activity_trend": activity_trend,
        "analysis_mode_distribution": analysis_mode_distribution,
        "recent_corrections": recent_corrections,
    }


def row_to_user(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None

    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "password_hash": row["password_hash"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


def row_to_correction(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "user_full_name": row["user_full_name"],
        "user_email": row["user_email"],
        "user_role": row["user_role"],
        "original_text": row["original_text"],
        "corrected_text": row["corrected_text"],
        "language": row["language"],
        "analysis_mode": row["analysis_mode"],
        "transformer_model": row["transformer_model"],
        "context_before": row["context_before"],
        "corrections": json.loads(row["corrections_json"] or "[]"),
        "stats": json.loads(row["stats_json"] or "{}"),
        "explanations": json.loads(row["explanations_json"] or "[]"),
        "keywords": json.loads(row["keywords_json"] or "[]"),
        "readability_score": row["readability_score"],
        "sentiment_label": row["sentiment_label"],
        "confidence_score": row["confidence_score"],
        "created_at": row["created_at"],
    }
