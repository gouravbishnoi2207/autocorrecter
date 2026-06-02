import re
from typing import Any, Dict

from werkzeug.security import check_password_hash, generate_password_hash


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match(normalize_email(email)))


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def build_user_context(user: Dict[str, Any] | None) -> Dict[str, Any]:
    if not user:
        return {"is_authenticated": False, "is_admin": False}

    return {
        "is_authenticated": True,
        "is_admin": user.get("role") == "admin",
        "current_user": user,
    }