from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditLog, LeadEvent, ProcessingJob


async def append_audit_log(
    session: AsyncSession,
    *,
    account_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    user_id: str | None = None,
    metadata_json: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        account_id=account_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        metadata_json=metadata_json,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(audit_log)
    await session.flush()
    return audit_log


async def append_lead_event(
    session: AsyncSession,
    *,
    account_id: str,
    lead_id: str,
    event_type: str,
    payload_json: dict | None = None,
) -> LeadEvent:
    lead_event = LeadEvent(
        account_id=account_id,
        lead_id=lead_id,
        event_type=event_type,
        payload_json=payload_json,
    )
    session.add(lead_event)
    await session.flush()
    return lead_event


async def next_job_version(session: AsyncSession, *, lead_id: str, job_type: str) -> int:
    stmt = select(func.count(ProcessingJob.id)).where(
        ProcessingJob.lead_id == lead_id,
        ProcessingJob.job_type == job_type,
    )
    current_count = await session.scalar(stmt)
    return int(current_count or 0) + 1


async def queue_processing_job(
    session: AsyncSession,
    *,
    account_id: str,
    lead_id: str,
    job_type: str,
    max_attempts: int = 3,
    scheduled_at: datetime | None = None,
) -> ProcessingJob:
    version = await next_job_version(session, lead_id=lead_id, job_type=job_type)
    processing_job = ProcessingJob(
        account_id=account_id,
        lead_id=lead_id,
        job_type=job_type,
        max_attempts=max_attempts,
        scheduled_at=scheduled_at or datetime.now(UTC),
        idempotency_key=f"{lead_id}:{job_type}:{version}",
    )
    session.add(processing_job)
    await session.flush()
    return processing_job
