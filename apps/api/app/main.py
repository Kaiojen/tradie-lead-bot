from __future__ import annotations

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.python.tradie_shared.db import build_session_factory
from shared.python.tradie_shared.logging import configure_logging
from shared.python.tradie_shared.settings import get_settings

from .core.errors import DomainError
from .core.request_context import CorrelationIdMiddleware
from .routers import account, enquiries, public, webhooks


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env)

    app = FastAPI(title="Tradie Lead Bot API", version="1.0.0")
    app.state.settings = settings
    app.state.session_factory = build_session_factory(settings)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(public.router)
    app.include_router(account.router)
    app.include_router(enquiries.router)
    app.include_router(webhooks.router)

    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        payload = {"error": exc.error}
        if exc.detail:
            payload["detail"] = exc.detail
        return JSONResponse(status_code=exc.status_code, content=payload)

    return app


app = create_app()
