"""User model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.credit_ledger import CreditLedger
    from app.models.generation import Generation
    from app.models.preset import Preset
    from app.models.project import Project


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    auth_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    auth_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    generations: Mapped[list[Generation]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    presets: Mapped[list[Preset]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    credit_entries: Mapped[list[CreditLedger]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
