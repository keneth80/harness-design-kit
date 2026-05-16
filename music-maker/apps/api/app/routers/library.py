"""/api/v1/library — cursor-paginated browse of the user's songs."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import db_session, get_current_user
from app.models.generation import Generation
from app.models.song import Song
from app.models.user import User
from app.schemas.library import LibraryItem, LibraryListResponse

router = APIRouter(prefix="/api/v1/library", tags=["library"])


def _encode_cursor(created_at: datetime, song_id: str) -> str:
    return base64.urlsafe_b64encode(
        json.dumps({"c": created_at.isoformat(), "i": song_id}).encode()
    ).decode()


def _decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    except (ValueError, json.JSONDecodeError):
        return {}


@router.get("", response_model=LibraryListResponse)
async def list_library(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
    favorites: bool = Query(default=False, alias="filter[favorites]"),
) -> LibraryListResponse:
    """Return the most recent songs owned by the current user."""

    stmt = (
        select(Song)
        .join(Generation, Generation.id == Song.generation_id)
        .where(Generation.user_id == user.id)
        .order_by(Song.created_at.desc(), Song.id.desc())
    )
    if favorites:
        stmt = stmt.where(Song.is_favorite.is_(True))
    if cursor:
        decoded = _decode_cursor(cursor)
        if "c" in decoded:
            anchor = datetime.fromisoformat(decoded["c"])
            stmt = stmt.where(
                and_(Song.created_at < anchor)
            )
    stmt = stmt.limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars().all())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last.created_at, str(last.id))
        rows = rows[:limit]

    items = [
        LibraryItem(
            id=s.id,
            generation_id=s.generation_id,
            variant=s.variant,
            title=None,
            duration_ms=s.duration_ms,
            cover_url=s.cover_url,
            mp3_url=s.mp3_url,
            is_favorite=s.is_favorite,
            tags=s.tags,
            created_at=s.created_at,
        )
        for s in rows
    ]
    return LibraryListResponse(items=items, next_cursor=next_cursor)
