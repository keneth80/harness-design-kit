"""Pydantic schemas for /lyrics endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LyricsGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=500)
    language: Literal["ko", "en"] = "ko"
    tone: str | None = Field(default="emotional", max_length=50)
    structure: list[str] = Field(
        default_factory=lambda: ["verse", "chorus", "verse", "chorus"],
        max_length=20,
    )
    syllables_per_line: int = Field(default=8, ge=4, le=20)


class ModerationResult(BaseModel):
    flagged: bool
    categories: list[str] = Field(default_factory=list)


class LyricsGenerateResponse(BaseModel):
    lyrics: str
    moderation: ModerationResult
    credit_cost: int = 0
