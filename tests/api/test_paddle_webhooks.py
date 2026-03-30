from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from apps.api.app.core.errors import DomainError
from apps.api.app.services.webhooks import (
    _extract_account_id,
    _extract_subscription_snapshot,
    _map_account_status,
    handle_paddle_webhook,
    validate_paddle_request,
)
from shared.python.tradie_shared.models import (
    Account,
    BillingEvent,
    BillingEventUnresolved,
    Subscription,
)


def _build_signature(secret: str, raw_body: bytes, timestamp: int) -> str:
    signed_payload = f"{timestamp}:{raw_body.decode('utf-8')}".encode()
    signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"ts={timestamp};h1={signature}"


def test_validate_paddle_request_accepts_valid_signature() -> None:
    secret = "paddle-secret"
    raw_body = b'{"event_id":"evt_123","event_type":"subscription.updated"}'
    timestamp = int(datetime.now(UTC).timestamp())

    validate_paddle_request(
        raw_body=raw_body,
        signature_header=_build_signature(secret, raw_body, timestamp),
        secret=secret,
    )


def test_validate_paddle_request_rejects_old_timestamp() -> None:
    secret = "paddle-secret"
    raw_body = b'{"event_id":"evt_123"}'
    stale_timestamp = int((datetime.now(UTC) - timedelta(minutes=6)).timestamp())

    with pytest.raises(DomainError) as exc_info:
        validate_paddle_request(
            raw_body=raw_body,
            signature_header=_build_signature(secret, raw_body, stale_timestamp),
            secret=secret,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.error == "invalid_webhook"


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.scalar_calls = 0

    async def scalar(self, _stmt):
        self.scalar_calls += 1
        return None

    def add(self, instance) -> None:
        self.added.append(instance)


class SequencedSession:
    def __init__(self, scalar_results) -> None:
        self._scalar_results = iter(scalar_results)
        self.added = []

    async def scalar(self, _stmt):
        return next(self._scalar_results)

    def add(self, instance) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        return None


def test_extract_account_id_uses_custom_data() -> None:
    payload = {
        "data": {
            "custom_data": {
                "account_id": "acc_123",
            }
        }
    }

    assert _extract_account_id(payload) == "acc_123"


def test_extract_subscription_snapshot_maps_dates_and_cancellation() -> None:
    payload = {
        "data": {
            "id": "sub_123",
            "customer_id": "cus_123",
            "custom_data": {"plan_code": "early_adopter"},
            "trial_ends_at": "2026-04-12T00:00:00Z",
            "current_billing_period": {"ends_at": "2026-04-30T00:00:00Z"},
            "scheduled_change": {"action": "cancel"},
        }
    }

    snapshot = _extract_subscription_snapshot(payload, event_type="subscription.updated")

    assert snapshot["provider_subscription_id"] == "sub_123"
    assert snapshot["provider_customer_id"] == "cus_123"
    assert snapshot["plan_code"] == "early_adopter"
    assert snapshot["cancel_at_period_end"] is True
    assert snapshot["trial_ends_at"] == datetime(2026, 4, 12, 0, 0, tzinfo=UTC)
    assert snapshot["current_period_end"] == datetime(2026, 4, 30, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("subscription_status", "account_status"),
    [
        ("trialing", "trial"),
        ("active", "active"),
        ("past_due", "suspended"),
        ("cancelled", "cancelled"),
    ],
)
def test_map_account_status(subscription_status: str, account_status: str) -> None:
    assert _map_account_status(subscription_status) == account_status


@pytest.mark.asyncio
async def test_handle_paddle_webhook_stores_unresolved_events() -> None:
    session = FakeSession()
    payload = {
        "event_id": "evt_orphan_123",
        "event_type": "subscription.updated",
        "data": {"subscription_id": "sub_missing"},
    }

    result = await handle_paddle_webhook(
        session,
        payload=payload,
        settings=SimpleNamespace(),
    )

    assert result == "ignored"
    assert len(session.added) == 1
    assert isinstance(session.added[0], BillingEventUnresolved)
    assert session.added[0].provider_event_id == "evt_orphan_123"


@pytest.mark.asyncio
async def test_handle_paddle_webhook_upserts_subscription_and_updates_account() -> None:
    account = Account(id="acc_123", business_name="Acme Plumbing", status="trial")
    session = SequencedSession(
        [
            None,  # no subscription found during account resolution
            None,  # no subscription found by provider_customer_id
            account,  # resolved account exists
            None,  # billing event not processed yet
            None,  # no existing subscription by provider_subscription_id
            None,  # no existing subscription by account_id
        ]
    )
    payload = {
        "event_id": "evt_sub_123",
        "event_type": "subscription.updated",
        "data": {
            "id": "sub_123",
            "customer_id": "cus_123",
            "status": "active",
            "custom_data": {
                "account_id": "acc_123",
                "plan_code": "early_adopter",
            },
            "current_billing_period": {"ends_at": "2026-04-30T00:00:00Z"},
        },
    }

    result = await handle_paddle_webhook(
        session,
        payload=payload,
        settings=SimpleNamespace(),
    )

    assert result == "ok"
    assert account.status == "active"
    assert account.plan_code == "early_adopter"
    assert any(isinstance(item, BillingEvent) for item in session.added)
    subscription = next(item for item in session.added if isinstance(item, Subscription))
    assert subscription.account_id == "acc_123"
    assert subscription.provider_subscription_id == "sub_123"
    assert subscription.provider_customer_id == "cus_123"
    assert subscription.status == "active"
    assert subscription.plan_code == "early_adopter"
