from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.python.tradie_shared.models import Lead, LeadNote
from shared.python.tradie_shared.operations import append_audit_log
from shared.python.tradie_shared.schemas import (
    LeadNoteCreateRequest,
    LeadNotesResponse,
    LeadNoteSummary,
)

from ..core.errors import DomainError


async def list_notes(
    session: AsyncSession,
    *,
    account_id: str,
    lead_id: str,
) -> LeadNotesResponse:
    notes = list(
        (
            await session.scalars(
                select(LeadNote)
                .where(LeadNote.account_id == account_id, LeadNote.lead_id == lead_id)
                .order_by(LeadNote.created_at.desc())
            )
        ).all()
    )
    return LeadNotesResponse(
        data=[
            LeadNoteSummary(
                id=note.id,
                user_id=note.user_id,
                content=note.content,
                created_at=note.created_at,
            )
            for note in notes
        ]
    )


async def create_note(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    lead_id: str,
    payload: LeadNoteCreateRequest,
    ip_address: str | None,
    user_agent: str | None,
) -> LeadNoteSummary:
    lead = await session.scalar(
        select(Lead).where(Lead.account_id == account_id, Lead.id == lead_id)
    )
    if lead is None:
        raise DomainError(404, "not_found")

    note = LeadNote(
        account_id=account_id,
        lead_id=lead_id,
        user_id=user_id,
        content=payload.content,
    )
    session.add(note)
    await session.flush()
    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="lead_note_created",
        entity_type="lead_note",
        entity_id=note.id,
        metadata_json={"lead_id": lead_id},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return LeadNoteSummary(
        id=note.id,
        user_id=note.user_id,
        content=note.content,
        created_at=note.created_at,
    )
