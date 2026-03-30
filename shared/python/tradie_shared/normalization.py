from __future__ import annotations

import html
import re

TAG_RE = re.compile(r"<[^>]+>")
NON_DIGIT_RE = re.compile(r"\D+")


def sanitize_text(value: str | None, *, max_length: int = 2_000) -> str | None:
    if value is None:
        return None
    stripped = TAG_RE.sub("", html.unescape(value)).strip()
    if not stripped:
        return None
    return stripped[:max_length]


def normalize_email(email: str | None) -> str | None:
    if email is None:
        return None
    normalized = email.strip().lower()
    return normalized or None


def normalize_au_mobile(phone: str) -> str:
    digits = NON_DIGIT_RE.sub("", phone)
    if digits.startswith("61") and len(digits) == 11:
        digits = f"0{digits[2:]}"
    if not digits.startswith("04") or len(digits) != 10:
        raise ValueError("customer_phone must be a valid Australian mobile number")
    return f"+61{digits[1:]}"
