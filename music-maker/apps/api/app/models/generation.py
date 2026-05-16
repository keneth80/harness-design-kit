"""Generation model — one request, may produce N songs (typically 2)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.song import Song
    from app.models.user import User


class GenerationStatus(enum.StrEnum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Generation(Base, TimestampMixin):
    __tablename__ = "generations"
    __table_args__ = (
        Index("ix_generations_user_created", "user_id", "created_at"),
        Index(
            "ix_generations_status_inflight",
            "status",
            "created_at",
            postgresql_where="status IN ('queued','processing')",
        ),
        Index("uq_generations_task_id", "task_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    preset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presets.id", ondelete="SET NULL"), nullable=True
    )
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GenerationStatus.queued.value
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="song")
    prompt: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    lyrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(50), nullable=False, default="auto")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mureka_trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    credit_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="generations")
    songs: Mapped[list[Song]] = relationship(
        back_populates="generation", cascade="all, delete-orphan"
    )
