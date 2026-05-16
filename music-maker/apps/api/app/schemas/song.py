"""Pydantic v2 schemas for /songs endpoints."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenerationStatus(enum.StrEnum):
    """Unified status — maps to and from Mureka task states.

    | Our value   | Mureka state           |
    |-------------|------------------------|
    | queued      | preparing              |
    | processing  | running                |
    | completed   | succeeded              |
    | failed      | failed                 |
    | cancelled   | cancelled              |
    """

    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class PromptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    length_s: int = Field(default=60, ge=10, le=300)
    genres: list[str] = Field(default_factory=list, max_length=10)
    moods: list[str] = Field(default_factory=list, max_length=10)
    bpm: int | None = Field(default=None, ge=30, le=240)
    key: str | None = Field(default=None, max_length=10)


class SongGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["song", "instrumental", "tts"] = "song"
    prompt: PromptInput
    lyrics: str | None = Field(default=None, max_length=10000)
    lyrics_mode: Literal["user", "ai", "none"] = "none"
    model: Literal["auto", "mureka-7", "mureka-o1"] = "auto"
    preset_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None

    @field_validator("lyrics")
    @classmethod
    def _lyrics_required_for_user_mode(cls, v: str | None, info) -> str | None:
        mode = info.data.get("lyrics_mode")
        if mode == "user" and (not v or not v.strip()):
            raise ValueError("lyrics is required when lyrics_mode='user'")
        return v


class SongGenerateResponse(BaseModel):
    """202 Accepted payload."""

    generation_id: uuid.UUID
    status: GenerationStatus
    estimated_seconds: int = 45
    credit_cost: int
    credits_remaining: int
    subscribe_url: str


class SongPublic(BaseModel):
    """Public representation of a completed Song."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant: str
    mp3_url: str | None = None
    wav_url: str | None = None
    cover_url: str | None = None
    duration_ms: int | None = None
    bpm: int | None = None
    key: str | None = None
    genres: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)


class SongStatusResponse(BaseModel):
    generation_id: uuid.UUID
    status: GenerationStatus
    progress: int = Field(ge=0, le=100)
    stage: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    estimated_remaining_s: int | None = None
    credit_cost: int
    songs: list[SongPublic] = Field(default_factory=list)
    lyrics: str | None = None
    error_code: str | None = None
    error_message: str | None = None
