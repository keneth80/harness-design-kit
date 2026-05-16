"""Sync SQLAlchemy session for Celery workers.

Celery tasks are synchronous; we use a separate sync engine derived from the
async DATABASE_URL by stripping the `+asyncpg` driver prefix.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def _sync_url(async_url: str) -> str:
    if async_url.startswith("postgresql+asyncpg://"):
        return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if async_url.startswith("sqlite+aiosqlite://"):
        return async_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return async_url


_engine = None
_factory = None


def _get_factory() -> sessionmaker[Session]:
    global _engine, _factory
    if _factory is None:
        settings = get_settings()
        _engine = create_engine(_sync_url(settings.database_url), pool_pre_ping=True, future=True)
        _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _factory


@contextmanager
def session_scope() -> Iterator[Session]:
    factory = _get_factory()
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
