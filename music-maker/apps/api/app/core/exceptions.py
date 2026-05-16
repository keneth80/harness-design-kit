"""Domain & infrastructure exceptions + RFC 7807 (Problem+JSON) handlers."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.tracing import get_trace_id

PROBLEM_BASE = "https://docs.music-maker.app/errors"


class DomainError(Exception):
    """Base class for domain errors that should be mapped to RFC 7807."""

    status_code: int = 400
    code: str = "domain_error"
    title: str = "Domain error"

    def __init__(self, detail: str | None = None, **extra: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        self.extra = extra


class InsufficientCreditsError(DomainError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    code = "insufficient_credits"
    title = "Insufficient credits"


class ModerationBlockedError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "moderation_blocked"
    title = "Content blocked by moderation"


class InvalidPromptError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid_prompt"
    title = "Invalid prompt"


class RateLimitedError(DomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limit_exceeded"
    title = "Rate limit exceeded"


class GenerationNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "generation_not_found"
    title = "Generation not found"


class NotAuthorisedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    title = "Forbidden"


# --- Mureka client errors ---


class MurekaError(Exception):
    """Top-level Mureka client error."""

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.code = code or "mureka_error"
        self.status_code = status_code


class MurekaTransientError(MurekaError):
    """Retryable (5xx, 429, network)."""


class MurekaPermanentError(MurekaError):
    """Non-retryable (4xx other than 429)."""


class MurekaTaskFailed(MurekaError):  # noqa: N818 — name matches architecture spec
    """Mureka task reported `failed` state."""


class MurekaTimeoutError(MurekaError):
    """Polling exceeded the configured max attempts."""


# --- Problem+JSON renderer ---


def _problem(
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    instance: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{PROBLEM_BASE}/{code}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "trace_id": get_trace_id(),
    }
    if extra:
        body.update(extra)
    return JSONResponse(
        status_code=status_code,
        content=body,
        media_type="application/problem+json",
        headers={"X-Trace-Id": get_trace_id()},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_handler(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(
            status_code=exc.status_code,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            instance=request.url.path,
            extra=exc.extra or None,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem(
            status_code=exc.status_code,
            code=f"http_{exc.status_code}",
            title=exc.detail if isinstance(exc.detail, str) else "HTTP error",
            detail=str(exc.detail),
            instance=request.url.path,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="validation_error",
            title="Validation error",
            detail="Request body failed validation",
            instance=request.url.path,
            extra={"errors": exc.errors()},
        )
