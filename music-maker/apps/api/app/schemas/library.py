"""Library list schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LibraryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    generation_id: uuid.UUID
    variant: str
    title: str | None = None
    duration_ms: int | None = None
    cover_url: str | None = None
    mp3_url: str | None = None
    is_favorite: bool = False
    tags: list[str] = Field(default_factory=list)
    created_at: datetime


class LibraryListResponse(BaseModel):
    items: list[LibraryItem]
    next_cursor: str | None = None
