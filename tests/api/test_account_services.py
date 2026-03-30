from __future__ import annotations

from datetime import UTC, datetime

from apps.api.app.services.accounts import (
    _extract_portal_session_url,
    _extract_supabase_user_id,
    _serialize_subscription_summary,
)
from shared.python.tradie_shared.models import Account, Subscription


def test_extract_portal_session_url_reads_customer_portal_overview() -> None:
    payload = {
        "data": {
            "urls": {
                "general": {
                    "overview": "https://billing.paddle.test/portal-session",
                }
            }
        }
    }

    assert _extract_portal_session_url(payload) == "https://billing.paddle.test/portal-session"


def test_extract_supabase_user_id_accepts_nested_user_payload() -> None:
    payload = {"user": {"id": "user_123"}}

    assert _extract_supabase_user_id(payload) == "user_123"


def test_serialize_subscription_summary_exposes_billing_actions() -> None:
    account = Account(id="acc_123", business_name="Acme Plumbing", status="active")
    subscription = Subscription(
        account_id="acc_123",
        status="active",
        plan_code="early_adopter",
        provider_customer_id="cus_123",
        provider_subscription_id="sub_123",
        current_period_end=datetime(2026, 4, 30, 0, 0, tzinfo=UTC),
    )

    summary = _serialize_subscription_summary(account=account, subscription=subscription)

    assert summary.can_manage_billing is True
    assert summary.can_cancel is True
    assert summary.current_period_end == datetime(2026, 4, 30, 0, 0, tzinfo=UTC)


def test_serialize_subscription_summary_hides_cancel_after_schedule() -> None:
    account = Account(id="acc_123", business_name="Acme Plumbing", status="active")
    subscription = Subscription(
        account_id="acc_123",
        status="active",
        plan_code="early_adopter",
        provider_customer_id="cus_123",
        provider_subscription_id="sub_123",
        cancel_at_period_end=True,
    )

    summary = _serialize_subscription_summary(account=account, subscription=subscription)

    assert summary.can_manage_billing is True
    assert summary.can_cancel is False
