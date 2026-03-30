from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.python.tradie_shared.models import Lead, LeadSource
from shared.python.tradie_shared.operations import (
    append_audit_log,
    append_lead_event,
    queue_processing_job,
)
from shared.python.tradie_shared.schemas import LeadIngestRequest
from shared.python.tradie_shared.security import SensitiveDataCipher, hash_sensitive_value
from shared.python.tradie_shared.settings import AppSettings

from ..core.errors import DomainError


async def ingest_lead(
    session: AsyncSession,
    *,
    payload: LeadIngestRequest,
    ip_address: str | None,
    user_agent: str | None,
    settings: AppSettings,
) -> str:
    lead_source = await session.scalar(
        select(LeadSource).where(
            LeadSource.external_key == payload.form_token,
            LeadSource.is_active.is_(True),
        )
    )
    if lead_source is None:
        raise DomainError(400, "invalid_payload", "Unknown form token")

    cipher = SensitiveDataCipher(settings.app_encryption_key)
    raw_text = payload.raw_message or payload.service_requested
    normalized_text = " | ".join(
        value
        for value in [
            payload.customer_name,
            payload.service_requested,
            payload.suburb,
            payload.raw_message,
        ]
        if value
    )
    lead = Lead(
        account_id=lead_source.account_id,
        lead_source_id=lead_source.id,
        customer_name=payload.customer_name,
        customer_phone=cipher.encrypt(payload.customer_phone),
        customer_email=cipher.encrypt(payload.customer_email) if payload.customer_email else None,
        customer_phone_hash=hash_sensitive_value(settings.app_hash_key, payload.customer_phone),
        customer_email_hash=hash_sensitive_value(settings.app_hash_key, payload.customer_email),
        suburb=payload.suburb,
        service_requested=payload.service_requested,
        raw_text=raw_text,
        normalized_text=normalized_text,
        consent_to_sms=payload.consent_to_sms,
        consent_captured_at=datetime.now(UTC) if payload.consent_to_sms else None,
    )
    session.add(lead)
    await session.flush()

    await append_lead_event(
        session,
        account_id=lead.account_id,
        lead_id=lead.id,
        event_type="received",
        payload_json={"source": "web_form", "lead_source_id": lead_source.id},
    )
    await append_audit_log(
        session,
        account_id=lead.account_id,
        action="lead_received",
        entity_type="lead",
        entity_id=lead.id,
        metadata_json={"lead_source_id": lead_source.id},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    processing_job = await queue_processing_job(
        session,
        account_id=lead.account_id,
        lead_id=lead.id,
        job_type="process_lead",
    )
    await append_audit_log(
        session,
        account_id=lead.account_id,
        action="processing_job_created",
        entity_type="processing_job",
        entity_id=processing_job.id,
        metadata_json={"job_type": processing_job.job_type, "lead_id": lead.id},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return lead.id
