"""Song model — one variant of a generation result."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.generation import Generation
    from app.models.stem import Stem


class Song(Base, TimestampMixin):
    __tablename__ = "songs"
    __table_args__ = (
        Index("ix_songs_generation", "generation_id"),
        Index("ix_songs_project", "project_id"),
        Index("ix_songs_mureka_uq", "mureka_song_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generations.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    mureka_song_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    variant: Mapped[str] = mapped_column(String(4), nullable=False, default="A")
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mp3_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    wav_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    key: Mapped[str | None] = mapped_column(String(10), nullable=True)
    genres: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    moods: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    generation: Mapped[Generation] = relationship(back_populates="songs")
    stems: Mapped[list[Stem]] = relationship(
        back_populates="song", cascade="all, delete-orphan"
    )
