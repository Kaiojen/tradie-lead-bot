from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .errors import DomainError


async def enforce_rate_limit(
    session: AsyncSession,
    *,
    bucket_key: str,
    limit: int,
    window_seconds: int = 60,
) -> None:
    now = datetime.now(UTC)
    window_start = now.replace(second=0, microsecond=0)
    expires_at = window_start + timedelta(seconds=window_seconds * 2)
    stmt = text(
        """
        insert into public.rate_limit_buckets (bucket_key, window_start, request_count, expires_at)
        values (:bucket_key, :window_start, 1, :expires_at)
        on conflict (bucket_key, window_start)
        do update
        set request_count = public.rate_limit_buckets.request_count + 1,
            expires_at = excluded.expires_at
        returning request_count
        """
    )
    result = await session.execute(
        stmt,
        {
            "bucket_key": bucket_key,
            "window_start": window_start,
            "expires_at": expires_at,
        },
    )
    request_count = int(result.scalar_one())
    if request_count > limit:
        raise DomainError(429, "rate_limited")
