from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from shared.python.tradie_shared.schemas import (
    AccountContext,
    ActionResponse,
    APIError,
    EnquiryDetail,
    EnquiryListResponse,
    EnquiryStatusUpdateRequest,
    LeadNoteCreateRequest,
    LeadNotesResponse,
    LeadNoteSummary,
)

from ..core.rate_limit import enforce_rate_limit
from ..dependencies.auth import get_account_context, require_owner
from ..dependencies.db import get_db_session
from ..services.enquiries import (
    get_enquiry_detail,
    list_enquiries,
    reprocess_enquiry,
    retry_failed_messages,
    update_enquiry_status,
)
from ..services.notes import create_note, list_notes

router = APIRouter(prefix="/api/enquiries", tags=["enquiries"])
AccountContextDependency = Annotated[AccountContext, Depends(get_account_context)]
OwnerContextDependency = Annotated[AccountContext, Depends(require_owner)]
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("", response_model=EnquiryListResponse, responses={401: {"model": APIError}})
async def list_enquiries_route(
    request: Request,
    account_context: AccountContextDependency,
    session: SessionDependency,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> EnquiryListResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"api:{account_context.user_id}",
        limit=request.app.state.settings.api_rate_limit_per_minute,
    )
    response = await list_enquiries(
        session,
        account_id=account_context.account_id,
        status=status_filter,
        page=page,
        limit=limit,
    )
    await session.commit()
    return response


@router.get("/{lead_id}", response_model=EnquiryDetail)
async def get_enquiry_detail_route(
    request: Request,
    lead_id: str,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> EnquiryDetail:
    await enforce_rate_limit(
        session,
        bucket_key=f"api:{account_context.user_id}",
        limit=request.app.state.settings.api_rate_limit_per_minute,
    )
    response = await get_enquiry_detail(
        session,
        account_id=account_context.account_id,
        lead_id=lead_id,
        settings=request.app.state.settings,
    )
    await session.commit()
    return response


@router.patch("/{lead_id}/status", response_model=ActionResponse)
async def update_enquiry_status_route(
    request: Request,
    lead_id: str,
    payload: EnquiryStatusUpdateRequest,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> ActionResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"api:{account_context.user_id}",
        limit=request.app.state.settings.api_rate_limit_per_minute,
    )
    response = await update_enquiry_status(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        lead_id=lead_id,
        payload=payload,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.post("/{lead_id}/retry", response_model=ActionResponse)
async def retry_enquiry_route(
    request: Request,
    lead_id: str,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> ActionResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"manual:{account_context.user_id}",
        limit=request.app.state.settings.manual_action_rate_limit_per_minute,
    )
    response = await retry_failed_messages(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        lead_id=lead_id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.post("/{lead_id}/reprocess", response_model=ActionResponse)
async def reprocess_enquiry_route(
    request: Request,
    lead_id: str,
    account_context: OwnerContextDependency,
    session: SessionDependency,
) -> ActionResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"manual:{account_context.user_id}",
        limit=request.app.state.settings.manual_action_rate_limit_per_minute,
    )
    response = await reprocess_enquiry(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        lead_id=lead_id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.get("/{lead_id}/notes", response_model=LeadNotesResponse)
async def list_notes_route(
    request: Request,
    lead_id: str,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> LeadNotesResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"api:{account_context.user_id}",
        limit=request.app.state.settings.api_rate_limit_per_minute,
    )
    response = await list_notes(
        session,
        account_id=account_context.account_id,
        lead_id=lead_id,
    )
    await session.commit()
    return response


@router.post("/{lead_id}/notes", response_model=LeadNoteSummary)
async def create_note_route(
    request: Request,
    lead_id: str,
    payload: LeadNoteCreateRequest,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> LeadNoteSummary:
    await enforce_rate_limit(
        session,
        bucket_key=f"manual:{account_context.user_id}",
        limit=request.app.state.settings.manual_action_rate_limit_per_minute,
    )
    response = await create_note(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        lead_id=lead_id,
        payload=payload,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response
