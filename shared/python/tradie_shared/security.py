from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken


class SensitiveDataCipher:
    def __init__(self, encryption_key: str) -> None:
        try:
            self._fernet = Fernet(encryption_key.encode("utf-8"))
        except ValueError as exc:  # pragma: no cover - defensive for invalid env
            raise ValueError("APP_ENCRYPTION_KEY must be a valid Fernet key") from exc

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:  # pragma: no cover - indicates configuration drift
            raise ValueError("Unable to decrypt sensitive field") from exc


def hash_sensitive_value(secret_key: str, value: str | None) -> str | None:
    if value is None:
        return None
    digest = hmac.new(secret_key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")


def mask_phone(phone: str | None) -> str | None:
    if phone is None:
        return None
    if len(phone) <= 4:
        return "*" * len(phone)
    return f"{'*' * (len(phone) - 4)}{phone[-4:]}"


def mask_email(email: str | None) -> str | None:
    if email is None:
        return None
    if "@" not in email:
        return "***"
    username, domain = email.split("@", 1)
    if len(username) <= 2:
        return f"{username[0]}***@{domain}"
    return f"{username[:2]}***@{domain}"
