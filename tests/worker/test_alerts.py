from __future__ import annotations

from types import SimpleNamespace

from apps.worker.app.main import (
    AIQualificationResult,
    build_tradie_alert_body,
    mask_message_body_for_logs,
)


def test_build_tradie_alert_body_uses_raw_form_fields_when_ai_fails() -> None:
    lead = SimpleNamespace(
        customer_name="Sam",
        suburb="Brisbane",
        service_requested="Blocked drain",
        raw_text="Kitchen sink overflowing",
    )

    body = build_tradie_alert_body(
        business_name="Acme Plumbing",
        lead=lead,
        customer_phone="0400 111 222",
        ai_result=None,
    )

    assert "Sam" in body
    assert "0400 111 222" in body
    assert "Brisbane" in body
    assert "Blocked drain" in body
    assert "Kitchen sink overflowing" in body


def test_build_tradie_alert_body_uses_ai_summary_when_available() -> None:
    lead = SimpleNamespace(
        customer_name="Sam",
        suburb="Brisbane",
        service_requested="Blocked drain",
        raw_text="Kitchen sink overflowing",
    )
    ai_result = AIQualificationResult(
        summary="Blocked drain in Brisbane. Customer available now.",
        urgency_level="high",
        extracted_fields={"name": "Sam", "service": "Blocked drain", "suburb": "Brisbane"},
    )

    body = build_tradie_alert_body(
        business_name="Acme Plumbing",
        lead=lead,
        customer_phone="0400 111 222",
        ai_result=ai_result,
    )

    assert "Urgency: high" in body
    assert "Blocked drain in Brisbane" in body


def test_mask_message_body_for_logs_masks_embedded_phone_numbers() -> None:
    masked = mask_message_body_for_logs(
        "New enquiry for Acme Plumbing. Name: Sam. Phone: 0400 111 222. Service: Blocked drain."
    )

    assert "0400 111 222" not in masked
    assert "1222" in masked
