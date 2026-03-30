from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.python.tradie_shared.schemas import LeadIngestRequest, LeadIngestResponse
from shared.python.tradie_shared.settings import AppSettings

from ..core.rate_limit import enforce_rate_limit
from ..dependencies.auth import get_settings
from ..dependencies.db import get_db_session
from ..services.lead_ingestion import ingest_lead

router = APIRouter(tags=["public"])


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/health", status_code=status.HTTP_200_OK)
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/api/leads/ingest",
    response_model=LeadIngestResponse,
    status_code=status.HTTP_200_OK,
)
async def ingest_lead_route(
    payload: LeadIngestRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> LeadIngestResponse:
    ip_address = _client_ip(request)
    await enforce_rate_limit(
        session,
        bucket_key=f"lead_capture:{ip_address}",
        limit=settings.lead_capture_rate_limit_per_minute,
    )
    lead_id = await ingest_lead(
        session,
        payload=payload,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
        settings=settings,
    )
    await session.commit()
    return LeadIngestResponse(lead_id=lead_id, status="received")
