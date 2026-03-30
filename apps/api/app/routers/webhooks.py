from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from shared.python.tradie_shared.settings import AppSettings

from ..core.rate_limit import enforce_rate_limit
from ..dependencies.auth import get_settings
from ..dependencies.db import get_db_session
from ..services.webhooks import (
    handle_paddle_webhook,
    handle_twilio_webhook,
    validate_paddle_request,
)

router = APIRouter(tags=["webhooks"])


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/webhooks/twilio", status_code=200)
async def twilio_webhook_route(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> dict[str, str]:
    await enforce_rate_limit(
        session,
        bucket_key=f"webhook:twilio:{_client_ip(request)}",
        limit=settings.webhook_rate_limit_per_minute,
    )
    await handle_twilio_webhook(session, request=request, settings=settings)
    await session.commit()
    return {"status": "ok"}


@router.post("/webhooks/paddle", status_code=200)
async def paddle_webhook_route(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> dict[str, str]:
    await enforce_rate_limit(
        session,
        bucket_key=f"webhook:paddle:{_client_ip(request)}",
        limit=settings.webhook_rate_limit_per_minute,
    )
    raw_body = await request.body()
    validate_paddle_request(
        raw_body=raw_body,
        signature_header=request.headers.get("Paddle-Signature"),
        secret=settings.paddle_webhook_secret,
    )
    payload = await request.json()
    status_value = await handle_paddle_webhook(session, payload=payload, settings=settings)
    await session.commit()
    return {"status": status_value}
