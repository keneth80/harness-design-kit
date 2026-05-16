"""Cleanup task — delete expired songs (30d) per architecture 6.5."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from app.models.song import Song
from app.services import storage as storage_svc
from app.workers._sync_db import session_scope
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(name="app.workers.cleanup_task.cleanup_expired_files")
def cleanup_expired_files(batch: int = 500) -> int:
    """Delete up to `batch` expired non-favourite, non-project-attached songs."""
    deleted = 0
    now = datetime.now(UTC)
    with session_scope() as session:
        stmt = (
            select(Song)
            .where(Song.expires_at.is_not(None))
            .where(Song.expires_at < now)
            .where(Song.is_favorite.is_(False))
            .where(Song.project_id.is_(None))
            .limit(batch)
        )
        rows = list(session.execute(stmt).scalars().all())
        for song in rows:
            storage_svc.delete(song.storage_key)
            session.delete(song)
            deleted += 1
    log.info("cleanup.done", deleted=deleted)
    return deleted
