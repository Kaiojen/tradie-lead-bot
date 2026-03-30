from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.request_validator import RequestValidator

from shared.python.tradie_shared.models import (
    Account,
    BillingEvent,
    BillingEventUnresolved,
    DeliveryStatusEvent,
    Message,
    Subscription,
)
from shared.python.tradie_shared.operations import append_audit_log, append_lead_event
from shared.python.tradie_shared.settings import AppSettings

from ..core.errors import DomainError

TWILIO_WEBHOOK_MAX_AGE = timedelta(minutes=5)


def _request_public_url(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    url = str(request.url)
    if forwarded_proto:
        url = url.replace(f"{request.url.scheme}://", f"{forwarded_proto}://", 1)
    if forwarded_host:
        url = url.replace(request.url.netloc, forwarded_host, 1)
    return url


def _get_nested(mapping: dict | None, *path: str):
    current = mapping
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _parse_provider_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _extract_account_id(payload: dict) -> str | None:
    data = payload.get("data") or {}
    candidates = (
        _get_nested(data, "custom_data", "account_id"),
        _get_nested(payload, "meta", "account_id"),
        payload.get("account_id"),
    )
    return next(
        (
            candidate
            for candidate in candidates
            if isinstance(candidate, str) and candidate.strip()
        ),
        None,
    )


def _extract_subscription_snapshot(payload: dict, *, event_type: str) -> dict[str, object | None]:
    data = payload.get("data") or {}
    scheduled_action = _get_nested(data, "scheduled_change", "action")
    status = data.get("status")

    if not status:
        if event_type.endswith(".canceled") or event_type.endswith(".cancelled"):
            status = "cancelled"
        elif event_type.endswith(".created"):
            status = "trialing"

    return {
        "provider_customer_id": data.get("customer_id"),
        "provider_subscription_id": data.get("id") or data.get("subscription_id"),
        "status": status,
        "plan_code": _get_nested(data, "custom_data", "plan_code") or data.get("plan_code"),
        "trial_ends_at": _parse_provider_datetime(data.get("trial_ends_at")),
        "current_period_end": _parse_provider_datetime(
            _get_nested(data, "current_billing_period", "ends_at") or data.get("next_billed_at")
        ),
        "cancel_at_period_end": bool(
            data.get("cancel_at_period_end") or scheduled_action == "cancel"
        ),
    }


def _map_account_status(subscription_status: str | None) -> str | None:
    if subscription_status in {"trialing", "trial"}:
        return "trial"
    if subscription_status == "active":
        return "active"
    if subscription_status in {"past_due", "paused"}:
        return "suspended"
    if subscription_status in {"cancelled", "canceled"}:
        return "cancelled"
    return None


def validate_twilio_request(
    *,
    request_date: str | None,
    request_url: str,
    form_items: dict[str, str],
    signature: str | None,
    auth_token: str | None,
) -> None:
    if not signature or not auth_token:
        raise DomainError(401, "invalid_webhook")
    if request_date:
        request_datetime = parsedate_to_datetime(request_date)
        if request_datetime.tzinfo is None:
            request_datetime = request_datetime.replace(tzinfo=UTC)
        if abs(datetime.now(UTC) - request_datetime.astimezone(UTC)) > TWILIO_WEBHOOK_MAX_AGE:
            raise DomainError(401, "invalid_webhook")
    validator = RequestValidator(auth_token)
    if not validator.validate(request_url, form_items, signature):
        raise DomainError(401, "invalid_webhook")


async def handle_twilio_webhook(
    session: AsyncSession,
    *,
    request: Request,
    settings: AppSettings,
) -> None:
    raw_body = await request.body()
    form_items = dict(parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True))
    validate_twilio_request(
        request_date=request.headers.get("Date"),
        request_url=_request_public_url(request),
        form_items=form_items,
        signature=request.headers.get("X-Twilio-Signature"),
        auth_token=settings.twilio_auth_token,
    )

    provider_message_id = form_items.get("MessageSid")
    provider_status = form_items.get("MessageStatus") or form_items.get("SmsStatus")
    if not provider_message_id or not provider_status:
        return

    message = await session.scalar(
        select(Message).where(Message.provider_message_id == provider_message_id)
    )
    if message is None:
        return

    session.add(
        DeliveryStatusEvent(
            account_id=message.account_id,
            message_id=message.id,
            provider=message.provider,
            provider_message_id=provider_message_id,
            status=provider_status,
            raw_payload_json=form_items,
        )
    )
    if provider_status in {"delivered", "failed", "undelivered"}:
        message.status = "failed" if provider_status == "failed" else provider_status

    await append_lead_event(
        session,
        account_id=message.account_id,
        lead_id=message.lead_id,
        event_type=f"twilio_{provider_status}",
        payload_json={"message_id": message.id, "provider_message_id": provider_message_id},
    )
    await append_audit_log(
        session,
        account_id=message.account_id,
        action="twilio_delivery_status_received",
        entity_type="message",
        entity_id=message.id,
        metadata_json={"status": provider_status, "provider_message_id": provider_message_id},
    )


def validate_paddle_request(
    *,
    raw_body: bytes,
    signature_header: str | None,
    secret: str | None,
) -> None:
    if not signature_header or not secret:
        raise DomainError(401, "invalid_webhook")
    signature_parts = {}
    for chunk in signature_header.split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        signature_parts[key.strip()] = value.strip()

    timestamp = signature_parts.get("ts")
    provided_signature = signature_parts.get("h1")
    if not timestamp or not provided_signature:
        raise DomainError(401, "invalid_webhook")

    timestamp_dt = datetime.fromtimestamp(int(timestamp), tz=UTC)
    if abs(datetime.now(UTC) - timestamp_dt) > timedelta(minutes=5):
        raise DomainError(401, "invalid_webhook")

    signed_payload = f"{timestamp}:{raw_body.decode('utf-8')}".encode()
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise DomainError(401, "invalid_webhook")


async def handle_paddle_webhook(
    session: AsyncSession,
    *,
    payload: dict,
    settings: AppSettings,
) -> str:
    event_id = payload.get("event_id") or payload.get("notification_id")
    event_type = payload.get("event_type") or payload.get("type") or "unknown"
    data = payload.get("data") or {}
    subscription_ref = data.get("id") or data.get("subscription_id")
    customer_ref = data.get("customer_id")
    account_id = None

    if subscription_ref:
        subscription = await session.scalar(
            select(Subscription).where(Subscription.provider_subscription_id == subscription_ref)
        )
        if subscription is not None:
            account_id = subscription.account_id
    if account_id is None and customer_ref:
        subscription = await session.scalar(
            select(Subscription).where(Subscription.provider_customer_id == customer_ref)
        )
        if subscription is not None:
            account_id = subscription.account_id
    if account_id is None:
        account_id = _extract_account_id(payload)

    if account_id is None or event_id is None:
        if event_id is not None:
            existing_unresolved = await session.scalar(
                select(BillingEventUnresolved).where(
                    BillingEventUnresolved.provider_event_id == event_id
                )
            )
            if existing_unresolved is None:
                session.add(
                    BillingEventUnresolved(
                        provider_event_id=event_id,
                        raw_payload_json=payload,
                    )
                )
        return "ignored"

    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        session.add(
            BillingEventUnresolved(
                provider_event_id=event_id,
                raw_payload_json=payload,
            )
        )
        return "ignored"

    existing = await session.scalar(
        select(BillingEvent).where(BillingEvent.provider_event_id == event_id)
    )
    if existing is not None:
        return "ok"

    snapshot = _extract_subscription_snapshot(payload, event_type=event_type)
    subscription = None
    provider_subscription_id = snapshot["provider_subscription_id"]
    if isinstance(provider_subscription_id, str) and provider_subscription_id:
        subscription = await session.scalar(
            select(Subscription).where(
                Subscription.provider_subscription_id == provider_subscription_id
            )
        )
    if subscription is None:
        subscription = await session.scalar(
            select(Subscription).where(Subscription.account_id == account_id)
        )
    if subscription is None:
        subscription = Subscription(
            account_id=account_id,
            status=(snapshot["status"] or "trialing"),
        )
        session.add(subscription)

    for field_name in (
        "provider_customer_id",
        "provider_subscription_id",
        "status",
        "plan_code",
        "trial_ends_at",
        "current_period_end",
        "cancel_at_period_end",
    ):
        field_value = snapshot[field_name]
        if field_value is None and field_name != "cancel_at_period_end":
            continue
        setattr(subscription, field_name, field_value)

    if subscription.plan_code:
        account.plan_code = subscription.plan_code
    mapped_account_status = _map_account_status(subscription.status)
    if mapped_account_status is not None:
        account.status = mapped_account_status

    billing_event = BillingEvent(
        account_id=account_id,
        event_type=event_type,
        provider_event_id=event_id,
        raw_payload_json=payload,
        processed_at=datetime.now(UTC),
        status="processed",
    )
    session.add(billing_event)
    await session.flush()
    await append_audit_log(
        session,
        account_id=account_id,
        action="billing_webhook_received",
        entity_type="billing_event",
        entity_id=billing_event.id,
        metadata_json={
            "event_type": event_type,
            "provider_event_id": event_id,
            "subscription_status": subscription.status,
        },
    )
    return "ok"
