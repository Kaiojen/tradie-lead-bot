from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.python.tradie_shared.models import Lead, LeadEvent, LeadNote, Message
from shared.python.tradie_shared.operations import (
    append_audit_log,
    append_lead_event,
    queue_processing_job,
)
from shared.python.tradie_shared.schemas import (
    ActionResponse,
    EnquiryDetail,
    EnquiryListItem,
    EnquiryListResponse,
    EnquiryStatusUpdateRequest,
    LeadNoteSummary,
    MessageSummary,
    PaginationMeta,
    TimelineEvent,
)
from shared.python.tradie_shared.security import SensitiveDataCipher
from shared.python.tradie_shared.settings import AppSettings

from ..core.errors import DomainError

FAILED_MESSAGE_STATUSES = ("failed", "undelivered")


def _build_message_delivery_flags(messages: Iterable[Message]) -> dict[str, bool]:
    has_failed_customer_sms = any(
        message.recipient_type == "lead" and message.status in FAILED_MESSAGE_STATUSES
        for message in messages
    )
    has_failed_tradie_sms = any(
        message.recipient_type == "tradie" and message.status in FAILED_MESSAGE_STATUSES
        for message in messages
    )
    return {
        "has_failed_sms": has_failed_customer_sms or has_failed_tradie_sms,
        "has_failed_customer_sms": has_failed_customer_sms,
        "has_failed_tradie_sms": has_failed_tradie_sms,
    }


async def _get_failed_message_flags_by_lead(
    session: AsyncSession,
    *,
    account_id: str,
    lead_ids: list[str],
) -> dict[str, dict[str, bool]]:
    if not lead_ids:
        return {}

    failed_messages = list(
        (
            await session.scalars(
                select(Message).where(
                    Message.account_id == account_id,
                    Message.lead_id.in_(lead_ids),
                    Message.status.in_(FAILED_MESSAGE_STATUSES),
                )
            )
        ).all()
    )

    flags_by_lead: dict[str, dict[str, bool]] = {
        lead_id: {
            "has_failed_sms": False,
            "has_failed_customer_sms": False,
            "has_failed_tradie_sms": False,
        }
        for lead_id in lead_ids
    }
    for message in failed_messages:
        flags = flags_by_lead[message.lead_id]
        flags["has_failed_sms"] = True
        if message.recipient_type == "lead":
            flags["has_failed_customer_sms"] = True
        if message.recipient_type == "tradie":
            flags["has_failed_tradie_sms"] = True

    return flags_by_lead


async def list_enquiries(
    session: AsyncSession,
    *,
    account_id: str,
    status: str | None,
    page: int,
    limit: int,
) -> EnquiryListResponse:
    base_stmt = select(Lead).where(Lead.account_id == account_id)
    if status:
        base_stmt = base_stmt.where(Lead.status == status)

    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = int(await session.scalar(total_stmt) or 0)

    leads = list(
        (
            await session.scalars(
                base_stmt.order_by(Lead.received_at.desc()).offset((page - 1) * limit).limit(limit)
            )
        ).all()
    )
    flags_by_lead = await _get_failed_message_flags_by_lead(
        session,
        account_id=account_id,
        lead_ids=[lead.id for lead in leads],
    )
    return EnquiryListResponse(
        data=[
            EnquiryListItem(
                id=lead.id,
                customer_name=lead.customer_name,
                suburb=lead.suburb,
                service_requested=lead.service_requested,
                status=lead.status,
                ai_status=lead.ai_status,
                urgency_level=lead.urgency_level,
                qualification_summary=lead.qualification_summary,
                needs_review=lead.ai_status == "failed",
                **flags_by_lead.get(
                    lead.id,
                    {
                        "has_failed_sms": False,
                        "has_failed_customer_sms": False,
                        "has_failed_tradie_sms": False,
                    },
                ),
                received_at=lead.received_at,
            )
            for lead in leads
        ],
        pagination=PaginationMeta(total=total, page=page, limit=limit),
    )


async def get_enquiry_detail(
    session: AsyncSession,
    *,
    account_id: str,
    lead_id: str,
    settings: AppSettings,
) -> EnquiryDetail:
    lead = await session.scalar(
        select(Lead).where(Lead.account_id == account_id, Lead.id == lead_id)
    )
    if lead is None:
        raise DomainError(404, "not_found")

    cipher = SensitiveDataCipher(settings.app_encryption_key)
    messages = list(
        (
            await session.scalars(
                select(Message)
                .where(Message.account_id == account_id, Message.lead_id == lead_id)
                .order_by(Message.created_at.asc())
            )
        ).all()
    )
    timeline = list(
        (
            await session.scalars(
                select(LeadEvent)
                .where(LeadEvent.account_id == account_id, LeadEvent.lead_id == lead_id)
                .order_by(LeadEvent.created_at.asc())
            )
        ).all()
    )
    notes = list(
        (
            await session.scalars(
                select(LeadNote)
                .where(LeadNote.account_id == account_id, LeadNote.lead_id == lead_id)
                .order_by(LeadNote.created_at.desc())
            )
        ).all()
    )
    delivery_flags = _build_message_delivery_flags(messages)
    return EnquiryDetail(
        id=lead.id,
        status=lead.status,
        ai_status=lead.ai_status,
        customer_name=lead.customer_name,
        customer_phone=cipher.decrypt(lead.customer_phone) or "",
        customer_email=cipher.decrypt(lead.customer_email) if lead.customer_email else None,
        suburb=lead.suburb,
        service_requested=lead.service_requested,
        urgency_level=lead.urgency_level,
        qualification_summary=lead.qualification_summary,
        needs_review=lead.ai_status == "failed",
        **delivery_flags,
        messages=[
            MessageSummary(
                id=message.id,
                recipient_type=message.recipient_type,
                status=message.status,
                body=message.body,
                created_at=message.created_at,
            )
            for message in messages
        ],
        timeline=[
            TimelineEvent(
                id=event.id,
                event_type=event.event_type,
                payload_json=event.payload_json,
                created_at=event.created_at,
            )
            for event in timeline
        ],
        notes=[
            LeadNoteSummary(
                id=note.id,
                user_id=note.user_id,
                content=note.content,
                created_at=note.created_at,
            )
            for note in notes
        ],
        is_possible_duplicate=lead.is_possible_duplicate,
        duplicate_of_lead_id=lead.duplicate_of_lead_id,
        received_at=lead.received_at,
        updated_at=lead.updated_at,
    )


async def update_enquiry_status(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    lead_id: str,
    payload: EnquiryStatusUpdateRequest,
    ip_address: str | None,
    user_agent: str | None,
) -> ActionResponse:
    lead = await session.scalar(
        select(Lead).where(Lead.account_id == account_id, Lead.id == lead_id)
    )
    if lead is None:
        raise DomainError(404, "not_found")

    lead.status = payload.status
    lead.updated_at = datetime.now(UTC)
    await append_lead_event(
        session,
        account_id=account_id,
        lead_id=lead.id,
        event_type=f"status_changed_to_{payload.status}",
        payload_json={"status": payload.status, "user_id": user_id},
    )
    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="enquiry_status_updated",
        entity_type="lead",
        entity_id=lead.id,
        metadata_json={"status": payload.status},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return ActionResponse(status="updated", lead_id=lead.id)


async def reprocess_enquiry(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    lead_id: str,
    ip_address: str | None,
    user_agent: str | None,
) -> ActionResponse:
    lead = await session.scalar(
        select(Lead).where(Lead.account_id == account_id, Lead.id == lead_id)
    )
    if lead is None:
        raise DomainError(404, "not_found")

    processing_job = await queue_processing_job(
        session,
        account_id=lead.account_id,
        lead_id=lead.id,
        job_type="process_lead",
    )
    await append_lead_event(
        session,
        account_id=account_id,
        lead_id=lead.id,
        event_type="reprocess_requested",
        payload_json={"user_id": user_id, "job_id": processing_job.id},
    )
    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="reprocess_requested",
        entity_type="lead",
        entity_id=lead.id,
        metadata_json={"job_id": processing_job.id},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return ActionResponse(status="queued", lead_id=lead.id, job_id=processing_job.id)


async def retry_failed_messages(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    lead_id: str,
    ip_address: str | None,
    user_agent: str | None,
) -> ActionResponse:
    lead = await session.scalar(
        select(Lead).where(Lead.account_id == account_id, Lead.id == lead_id)
    )
    if lead is None:
        raise DomainError(404, "not_found")

    failed_count = int(
        await session.scalar(
            select(func.count(Message.id)).where(
                Message.account_id == account_id,
                Message.lead_id == lead_id,
                Message.status.in_(FAILED_MESSAGE_STATUSES),
            )
        )
        or 0
    )
    if failed_count == 0:
        raise DomainError(400, "no_failed_messages")

    processing_job = await queue_processing_job(
        session,
        account_id=lead.account_id,
        lead_id=lead.id,
        job_type="send_sms",
    )
    await append_lead_event(
        session,
        account_id=account_id,
        lead_id=lead.id,
        event_type="retry_requested",
        payload_json={"user_id": user_id, "job_id": processing_job.id},
    )
    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="retry_requested",
        entity_type="lead",
        entity_id=lead.id,
        metadata_json={"job_id": processing_job.id},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return ActionResponse(status="queued", lead_id=lead.id, job_id=processing_job.id)
