from __future__ import annotations

from cryptography.fernet import Fernet

from shared.python.tradie_shared.normalization import (
    normalize_au_mobile,
    normalize_email,
    sanitize_text,
)
from shared.python.tradie_shared.schemas import LeadIngestRequest
from shared.python.tradie_shared.security import (
    SensitiveDataCipher,
    hash_sensitive_value,
    mask_email,
    mask_phone,
)


def test_lead_ingest_request_normalizes_and_sanitizes_fields() -> None:
    payload = LeadIngestRequest(
        form_token="formtoken-123",
        customer_name=" <b>Jane Smith</b> ",
        customer_phone="0412 345 678",
        customer_email=" JANE@EXAMPLE.COM ",
        suburb=" <i>Brisbane</i> ",
        service_requested="Blocked drain",
        raw_message="<script>ignore</script>Need help today",
    )

    assert payload.customer_name == "Jane Smith"
    assert payload.customer_phone == "+61412345678"
    assert payload.customer_email == "jane@example.com"
    assert payload.suburb == "Brisbane"
    assert payload.raw_message == "ignoreNeed help today"


def test_security_helpers_encrypt_hash_and_mask() -> None:
    cipher = SensitiveDataCipher(Fernet.generate_key().decode("utf-8"))
    encrypted = cipher.encrypt("+61412345678")

    assert encrypted is not None
    assert encrypted != "+61412345678"
    assert cipher.decrypt(encrypted) == "+61412345678"
    assert hash_sensitive_value("secret", "+61412345678") == hash_sensitive_value(
        "secret",
        "+61412345678",
    )
    assert mask_phone("+61412345678").endswith("5678")
    assert mask_email("jane@example.com") == "ja***@example.com"


def test_low_level_normalizers_match_au_rules() -> None:
    assert sanitize_text("<b>Hello</b>") == "Hello"
    assert normalize_email(" USER@EXAMPLE.COM ") == "user@example.com"
    assert normalize_au_mobile("61412345678") == "+61412345678"
