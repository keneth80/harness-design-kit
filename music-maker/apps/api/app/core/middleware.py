"""Trace-id middleware: assigns a trace id per request and echoes it back."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.tracing import new_trace_id, set_trace_id


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Read `X-Trace-Id` from incoming request (or mint a new one) and propagate."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        incoming = request.headers.get("x-trace-id") or new_trace_id()
        set_trace_id(incoming)
        response: Response = await call_next(request)
        response.headers["X-Trace-Id"] = incoming
        return response
