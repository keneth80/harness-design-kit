"""Celery task that submits a Mureka job, polls until completion, persists.

Faithful implementation of `docs/03-Architecture.md` section 5.2.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime

import structlog

from app.config import get_settings
from app.core.exceptions import (
    MurekaPermanentError,
    MurekaTaskFailed,
    MurekaTimeoutError,
    MurekaTransientError,
)
from app.models.generation import Generation, GenerationStatus
from app.models.song import Song
from app.services import credits as credits_svc
from app.services import storage as storage_svc
from app.services.mureka_client import MurekaClient, MurekaTaskStatus
from app.services.sse_hub import publish_sync
from app.workers._sync_db import session_scope
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


# ---- helpers (sync, designed for testability) ----


def _run_async(coro):
    """Run a coroutine from sync code, even if a loop already exists."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Edge case: not expected inside Celery worker, but be safe.
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _mureka_call(coro):
    return _run_async(coro)


def _publish(generation_id: str, payload: dict) -> None:
    try:
        publish_sync(generation_id, payload)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "worker.publish_failed", generation_id=generation_id, error=str(exc)
        )


def _persist_songs(
    *,
    session,
    generation: Generation,
    status: MurekaTaskStatus,
    audio_bytes: list[bytes],
) -> list[Song]:
    songs: list[Song] = []
    for idx, item in enumerate(status.items[:2]):  # variants A,B
        variant = "AB"[idx] if idx < 2 else str(idx)
        key = storage_svc.storage_key_for_song(str(generation.id), variant, "mp3")
        put = storage_svc.put_bytes(key, audio_bytes[idx], content_type="audio/mpeg")
        song = Song(
            generation_id=generation.id,
            project_id=generation.project_id,
            mureka_song_id=item.id,
            variant=variant,
            storage_key=put.key,
            mp3_url=put.url,
            cover_url=item.cover_url,
            duration_ms=item.duration_ms,
            bpm=item.bpm,
            key=item.key,
            genres=list(item.genres or []),
            moods=list(item.moods or []),
        )
        session.add(song)
        songs.append(song)
    session.flush()
    return songs


# ---- main task ----


@celery_app.task(
    bind=True,
    name="app.workers.poll_task.run_generation",
    max_retries=2,
    acks_late=True,
)
def run_generation(self, generation_id: str) -> None:
    """Submit + poll Mureka, persist results, manage credit saga."""
    settings = get_settings()
    gen_uuid = uuid.UUID(generation_id)
    log.info("worker.start", generation_id=generation_id)

    with session_scope() as session:
        gen = session.get(Generation, gen_uuid)
        if gen is None:
            log.warning("worker.generation_missing", generation_id=generation_id)
            return
        if gen.status in (GenerationStatus.completed.value, GenerationStatus.failed.value):
            log.info("worker.already_done", generation_id=generation_id, status=gen.status)
            return

        user_id = gen.user_id
        credit_cost = gen.credit_cost

        try:
            client = MurekaClient(settings)
            try:
                # 1) submit
                task = _mureka_call(
                    client.generate_song(
                        lyrics=gen.lyrics,
                        prompt=gen.prompt.get("text", ""),
                        model=gen.model,
                        length_s=gen.prompt.get("length_s", 60),
                    )
                )
                gen.task_id = task.task_id
                gen.mureka_trace_id = task.trace_id
                gen.status = GenerationStatus.processing.value
                gen.progress = 10
                session.flush()
                _publish(
                    generation_id,
                    {"event": "progress", "progress": 10, "stage": "submitted"},
                )

                # 2) poll
                final_status: MurekaTaskStatus | None = None
                for i in range(settings.mureka_poll_max_count):
                    time.sleep(settings.mureka_poll_interval_s)
                    status = _mureka_call(client.query_task(task.task_id))
                    progress = min(10 + int(i * 1.5), 95)
                    gen.progress = progress
                    session.flush()
                    _publish(
                        generation_id,
                        {
                            "event": "progress",
                            "progress": progress,
                            "stage": status.stage,
                        },
                    )
                    if status.state == "completed":
                        final_status = status
                        break
                    if status.state == "failed":
                        raise MurekaTaskFailed(
                            status.error_message or "mureka task failed",
                            code=status.error_code or "mureka_task_failed",
                        )

                if final_status is None:
                    raise MurekaTimeoutError(
                        "polling exceeded max attempts",
                        code="poll_timeout",
                    )

                # 3) download + upload
                audio = [
                    _mureka_call(client.download_audio(item.url))
                    for item in final_status.items[:2]
                ]
            finally:
                _mureka_call(client.aclose())

            songs = _persist_songs(
                session=session,
                generation=gen,
                status=final_status,
                audio_bytes=audio,
            )

            # 4) finalise generation + credits
            gen.status = GenerationStatus.completed.value
            gen.progress = 100
            gen.completed_at = datetime.now(UTC)
            credits_svc.commit_sync(
                session,
                user_id=user_id,
                amount=credit_cost,
                generation_id=gen.id,
            )
            session.flush()

            _publish(
                generation_id,
                {
                    "event": "completed",
                    "songs": [
                        {
                            "id": str(s.id),
                            "variant": s.variant,
                            "mp3_url": s.mp3_url,
                            "duration_ms": s.duration_ms,
                            "bpm": s.bpm,
                            "key": s.key,
                            "cover_url": s.cover_url,
                        }
                        for s in songs
                    ],
                },
            )
            log.info("worker.completed", generation_id=generation_id)

        except (MurekaTransientError, MurekaTaskFailed, MurekaTimeoutError) as exc:
            if self.request.retries < self.max_retries:
                log.warning(
                    "worker.retry",
                    generation_id=generation_id,
                    attempt=self.request.retries + 1,
                    error=str(exc),
                )
                _publish(
                    generation_id,
                    {"event": "retrying", "attempt": self.request.retries + 1},
                )
                # NOTE: we rollback by raising; commit will not happen.
                # Celery will re-dispatch.
                session.rollback()
                raise self.retry(
                    exc=exc, countdown=(2 ** self.request.retries) * 2
                ) from exc
            credits_svc.refund_sync(
                session,
                user_id=user_id,
                amount=credit_cost,
                generation_id=gen.id,
                reason=f"refund:{exc}",
            )
            gen.status = GenerationStatus.failed.value
            gen.error_code = getattr(exc, "code", "unknown")
            gen.error_message = str(exc)
            session.flush()
            _publish(
                generation_id,
                {
                    "event": "failed",
                    "error": gen.error_code,
                    "refunded": credit_cost,
                },
            )
            log.error(
                "worker.failed",
                generation_id=generation_id,
                error=str(exc),
                code=gen.error_code,
            )
        except MurekaPermanentError as exc:
            credits_svc.refund_sync(
                session,
                user_id=user_id,
                amount=credit_cost,
                generation_id=gen.id,
                reason=f"refund_permanent:{exc.code}",
            )
            gen.status = GenerationStatus.failed.value
            gen.error_code = exc.code
            gen.error_message = str(exc)
            session.flush()
            _publish(
                generation_id,
                {"event": "failed", "error": exc.code, "refunded": credit_cost},
            )
            log.error(
                "worker.permanent_failure",
                generation_id=generation_id,
                code=exc.code,
            )
