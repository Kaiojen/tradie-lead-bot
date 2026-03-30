from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest

from apps.api.app.core.errors import DomainError
from apps.api.app.services.webhooks import validate_twilio_request


def test_validate_twilio_request_rejects_stale_date() -> None:
    stale_date = format_datetime(datetime.now(UTC) - timedelta(minutes=6))

    with pytest.raises(DomainError) as exc_info:
        validate_twilio_request(
            request_date=stale_date,
            request_url="https://example.com/webhooks/twilio",
            form_items={"MessageSid": "SM123", "MessageStatus": "delivered"},
            signature="signature",
            auth_token="token",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.error == "invalid_webhook"
