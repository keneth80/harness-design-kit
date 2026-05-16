"""Trace-id helpers — per-request and Mureka call correlation."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def new_trace_id() -> str:
    return uuid.uuid4().hex


def get_trace_id() -> str:
    tid = trace_id_var.get()
    return tid or ""


def set_trace_id(tid: str) -> None:
    trace_id_var.set(tid)
