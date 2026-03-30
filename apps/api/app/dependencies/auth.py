from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.python.tradie_shared.models import AccountMembership
from shared.python.tradie_shared.schemas import AccountContext, AuthIdentity
from shared.python.tradie_shared.settings import AppSettings

from ..core.errors import DomainError
from .db import get_db_session

bearer_scheme = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> AppSettings:
    return request.app.state.settings


async def get_auth_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> AuthIdentity:
    if credentials is None:
        raise DomainError(401, "auth_required")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise DomainError(401, "invalid_token", str(exc)) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise DomainError(401, "invalid_token", "Token missing subject")
    return AuthIdentity(user_id=user_id, email=payload.get("email"))


async def get_account_context(
    request: Request,
    identity: Annotated[AuthIdentity, Depends(get_auth_identity)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountContext:
    requested_account_id = request.state.requested_account_id
    stmt = select(AccountMembership).where(AccountMembership.user_id == identity.user_id)
    if requested_account_id:
        stmt = stmt.where(AccountMembership.account_id == requested_account_id)
    memberships = list((await session.scalars(stmt)).all())
    if not memberships:
        raise DomainError(403, "account_forbidden")
    if requested_account_id is None and len(memberships) > 1:
        raise DomainError(
            400,
            "account_required",
            "X-Account-Id header is required for users with multiple accounts",
        )

    membership = memberships[0]
    if membership.accepted_at is None:
        membership.accepted_at = datetime.now(UTC)
    await session.execute(
        text("select set_config('app.current_account_id', :account_id, true)"),
        {"account_id": membership.account_id},
    )
    request.state.account_id = membership.account_id
    return AccountContext(
        account_id=membership.account_id,
        user_id=identity.user_id,
        role=membership.role,
    )


async def require_owner(
    account_context: Annotated[AccountContext, Depends(get_account_context)],
) -> AccountContext:
    if account_context.role != "owner":
        raise DomainError(403, "owner_required")
    return account_context
