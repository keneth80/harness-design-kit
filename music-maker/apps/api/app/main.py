"""FastAPI application factory."""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import TraceIdMiddleware
from app.routers import account, health, library, lyrics, songs

log = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="Mureka Studio API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    app.add_middleware(TraceIdMiddleware)
    register_exception_handlers(app)

    # Sentry (optional)
    if settings.sentry_dsn_api:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration

            sentry_sdk.init(
                dsn=settings.sentry_dsn_api,
                environment=settings.app_env,
                integrations=[FastApiIntegration()],
                traces_sample_rate=0.1,
            )
        except ImportError:
            log.warning("sentry_sdk_unavailable")

    app.include_router(health.router)
    app.include_router(songs.router)
    app.include_router(lyrics.router)
    app.include_router(library.router)
    app.include_router(account.router)

    @app.on_event("startup")
    async def _startup() -> None:
        log.info("api.startup", env=settings.app_env, service=settings.service_name)

    return app


app = create_app()
