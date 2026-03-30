from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from shared.python.tradie_shared.logging import bind_correlation_id


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = bind_correlation_id(request.headers.get("X-Request-ID"))
        request.state.correlation_id = correlation_id
        request.state.requested_account_id = request.headers.get("X-Account-Id")
        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        return response
