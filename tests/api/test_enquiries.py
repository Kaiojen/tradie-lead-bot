from __future__ import annotations

from types import SimpleNamespace

from apps.api.app.services.enquiries import _build_message_delivery_flags


def test_build_message_delivery_flags_marks_customer_and_tradie_failures() -> None:
    flags = _build_message_delivery_flags(
        [
            SimpleNamespace(recipient_type="lead", status="failed"),
            SimpleNamespace(recipient_type="tradie", status="undelivered"),
            SimpleNamespace(recipient_type="tradie", status="delivered"),
        ]
    )

    assert flags == {
        "has_failed_sms": True,
        "has_failed_customer_sms": True,
        "has_failed_tradie_sms": True,
    }


def test_build_message_delivery_flags_ignores_successful_messages() -> None:
    flags = _build_message_delivery_flags(
        [
            SimpleNamespace(recipient_type="lead", status="queued"),
            SimpleNamespace(recipient_type="tradie", status="delivered"),
        ]
    )

    assert flags == {
        "has_failed_sms": False,
        "has_failed_customer_sms": False,
        "has_failed_tradie_sms": False,
    }
