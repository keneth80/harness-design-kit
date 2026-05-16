"""/api/v1/songs — generation request, status, SSE stream."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    GenerationNotFoundError,
    InvalidPromptError,
    ModerationBlockedError,
    NotAuthorisedError,
)
from app.deps import db_session, get_current_user
from app.models.generation import Generation, GenerationStatus
from app.models.song import Song
from app.models.user import User
from app.schemas.song import (
    GenerationStatus as GenerationStatusSchema,
)
from app.schemas.song import (
    SongGenerateRequest,
    SongGenerateResponse,
    SongPublic,
    SongStatusResponse,
)
from app.services import credits, moderation
from app.services.sse_hub import subscribe

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/songs", tags=["songs"])


def _credit_cost_for(request: SongGenerateRequest, default_cost: int) -> int:
    # MVP: flat. Premium models could be more expensive.
    if request.model == "mureka-o1":
        return default_cost * 2
    return default_cost


def _enqueue(generation_id: uuid.UUID) -> None:
    """Best-effort enqueue. In tests this is monkey-patched."""
    try:
        from app.workers.poll_task import run_generation

        run_generation.delay(str(generation_id))
    except Exception as exc:  # noqa: BLE001
        log.warning("songs.enqueue_failed", generation_id=str(generation_id), error=str(exc))


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SongGenerateResponse,
)
async def create_generation(
    body: SongGenerateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> SongGenerateResponse:
    """Create a generation: validate -> moderate -> hold credit -> enqueue."""
    from app.config import get_settings

    settings = get_settings()

    # 1) lyrics moderation (optional)
    if body.lyrics:
        decision = await moderation.check_text(body.lyrics)
        if decision.flagged:
            raise ModerationBlockedError(
                detail="lyrics blocked by moderation",
                categories=list(decision.categories),
            )
    if body.prompt.text:
        decision = await moderation.check_text(body.prompt.text)
        if decision.flagged:
            raise ModerationBlockedError(
                detail="prompt blocked by moderation",
                categories=list(decision.categories),
            )

    # 2) prompt sanity
    if not body.prompt.text.strip():
        raise InvalidPromptError(detail="prompt text required")

    cost = _credit_cost_for(body, settings.generation_default_cost)

    # 3) create generation row first (so credit ledger can reference it)
    gen = Generation(
        user_id=user.id,
        project_id=body.project_id,
        preset_id=body.preset_id,
        mode=body.mode,
        prompt=body.prompt.model_dump(),
        lyrics=body.lyrics,
        model=body.model,
        status=GenerationStatus.queued.value,
        credit_cost=cost,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    session.add(gen)
    await session.flush()  # gen.id populated

    # 4) hold credit (raises InsufficientCreditsError -> 402)
    await credits.hold(
        session,
        user_id=user.id,
        amount=cost,
        generation_id=gen.id,
        reason="song_generation_hold",
    )

    await session.commit()
    await session.refresh(gen)

    # 5) enqueue worker
    _enqueue(gen.id)

    remaining = await credits.get_balance(session, user.id)
    return SongGenerateResponse(
        generation_id=gen.id,
        status=GenerationStatusSchema.queued,
        estimated_seconds=45,
        credit_cost=cost,
        credits_remaining=remaining,
        subscribe_url=f"/api/v1/songs/{gen.id}/stream",
    )


@router.get("/{generation_id}", response_model=SongStatusResponse)
async def get_generation(
    generation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> SongStatusResponse:
    gen = await session.get(Generation, generation_id)
    if gen is None:
        raise GenerationNotFoundError()
    if gen.user_id != user.id:
        raise NotAuthorisedError()

    songs_result = await session.execute(
        select(Song).where(Song.generation_id == generation_id).order_by(Song.variant)
    )
    songs = list(songs_result.scalars().all())

    return SongStatusResponse(
        generation_id=gen.id,
        status=GenerationStatusSchema(gen.status),
        progress=gen.progress,
        stage=None,
        started_at=gen.created_at,
        completed_at=gen.completed_at,
        credit_cost=gen.credit_cost,
        songs=[SongPublic.model_validate(s) for s in songs],
        lyrics=gen.lyrics,
        error_code=gen.error_code,
        error_message=gen.error_message,
    )


@router.get("/{generation_id}/stream")
async def stream_generation(
    generation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> StreamingResponse:
    """SSE stream of progress events. 25s ping keep-alive."""
    gen = await session.get(Generation, generation_id)
    if gen is None:
        raise GenerationNotFoundError()
    if gen.user_id != user.id:
        raise NotAuthorisedError()

    async def event_stream():
        yield ": connected\n\n"
        sub = subscribe(str(generation_id)).__aiter__()
        while True:
            try:
                payload = await asyncio.wait_for(sub.__anext__(), timeout=25.0)
                yield f"data: {json.dumps(payload, default=str)}\n\n"
                if payload.get("event") in ("completed", "failed"):
                    break
            except TimeoutError:
                yield 'data: {"event":"ping"}\n\n'
            except StopAsyncIteration:
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
