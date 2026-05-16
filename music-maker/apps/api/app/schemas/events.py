"""SSE event envelopes (used by SSE hub / docstrings)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProgressEvent(BaseModel):
    event: Literal["progress"] = "progress"
    progress: int = Field(ge=0, le=100)
    stage: str | None = None
    estimated_remaining_s: int | None = None


class CompletedEvent(BaseModel):
    event: Literal["completed"] = "completed"
    songs: list[dict] = Field(default_factory=list)


class FailedEvent(BaseModel):
    event: Literal["failed"] = "failed"
    error: str
    refunded: int = 0


class RetryingEvent(BaseModel):
    event: Literal["retrying"] = "retrying"
    attempt: int


class PingEvent(BaseModel):
    event: Literal["ping"] = "ping"
