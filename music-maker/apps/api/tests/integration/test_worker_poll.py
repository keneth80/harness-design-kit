"""Integration: poll_task worker happy path (Mureka + storage + SSE mocked).

Worker code is sync, the rest of the app is async. We bridge them by routing
both to a single sqlite **file** (not :memory:) so the sync and async engines
share the same physical DB.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def worker_db(monkeypatch):
    """Spin up a shared sqlite file used by both async (test setup) and sync (worker)."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    async_url = f"sqlite+aiosqlite:///{path}"
    sync_url = f"sqlite:///{path}"
    monkeypatch.setenv("DATABASE_URL", async_url)

    # Reset settings + engines
    from app.config import get_settings

    get_settings.cache_clear()
    from app import db as app_db
    from app.workers import _sync_db as worker_db_mod

    app_db._engine = None
    app_db._session_factory = None
    worker_db_mod._engine = None  # type: ignore[attr-defined]
    worker_db_mod._factory = None  # type: ignore[attr-defined]

    # Build schema
    from sqlalchemy import create_engine

    from app.models import Base

    sync_engine = create_engine(sync_url)
    Base.metadata.create_all(sync_engine)

    yield {"async_url": async_url, "sync_url": sync_url, "path": path, "sync_engine": sync_engine}

    sync_engine.dispose()
    try:
        os.unlink(path)
    except OSError:
        pass
    # Reset for other tests
    get_settings.cache_clear()
    app_db._engine = None
    app_db._session_factory = None
    worker_db_mod._engine = None  # type: ignore[attr-defined]
    worker_db_mod._factory = None  # type: ignore[attr-defined]


def _seed(sync_engine, user_id: uuid.UUID, gen_id: uuid.UUID) -> None:
    from sqlalchemy.orm import Session

    from app.models.credit_ledger import CreditLedger
    from app.models.generation import Generation
    from app.models.user import User

    with Session(sync_engine) as s:
        s.add(User(id=user_id, email=f"u-{user_id.hex[:6]}@x.y", plan="pro", credits=10))
        s.add(CreditLedger(id=uuid.uuid4(), user_id=user_id, type="grant", amount=10))
        s.add(
            Generation(
                id=gen_id,
                user_id=user_id,
                mode="song",
                prompt={"text": "test", "length_s": 30},
                model="auto",
                status="queued",
                credit_cost=1,
            )
        )
        s.add(
            CreditLedger(
                id=uuid.uuid4(),
                user_id=user_id,
                generation_id=gen_id,
                type="hold",
                amount=-1,
            )
        )
        s.commit()


def test_run_generation_happy_path_persists_songs_and_charges(worker_db):
    user_id = uuid.uuid4()
    gen_id = uuid.uuid4()
    _seed(worker_db["sync_engine"], user_id, gen_id)

    # Mock external mureka client
    from app.services.mureka_client import (
        MurekaTaskItem,
        MurekaTaskStatus,
        TaskResponse,
    )

    fake = MagicMock()

    async def _gen_song(**_kw):
        return TaskResponse(task_id="task_x", state="pending", trace_id="t1")

    async def _query(_tid):
        return MurekaTaskStatus(
            task_id="task_x",
            state="completed",
            items=[
                MurekaTaskItem(id="s1", url="http://m/A.mp3", duration_ms=30000, bpm=90, key="Cm"),
                MurekaTaskItem(id="s2", url="http://m/B.mp3", duration_ms=30000),
            ],
        )

    async def _download(_url):
        return b"fake-audio"

    async def _close():
        return None

    fake.generate_song.side_effect = lambda **kw: _gen_song(**kw)
    fake.query_task.side_effect = _query
    fake.download_audio.side_effect = _download
    fake.aclose.side_effect = _close

    from app.workers import poll_task as poll_mod

    # Shorten poll loop
    poll_mod.get_settings().mureka_poll_max_count = 2  # type: ignore[misc]
    poll_mod.get_settings().mureka_poll_interval_s = 0  # type: ignore[misc]

    with (
        patch.object(poll_mod, "MurekaClient", return_value=fake),
        patch.object(
            poll_mod.storage_svc,
            "put_bytes",
            return_value=MagicMock(key="k", url="http://cdn/k", bucket="b"),
        ),
        patch.object(poll_mod, "_publish") as pub,
        patch("time.sleep", lambda _x: None),
    ):
        poll_mod.run_generation.run(str(gen_id))

    # Assertions via sync session
    from sqlalchemy.orm import Session

    from app.models.credit_ledger import CreditLedger
    from app.models.generation import Generation
    from app.models.song import Song

    with Session(worker_db["sync_engine"]) as s:
        gen = s.get(Generation, gen_id)
        assert gen is not None
        assert gen.status == "completed"
        assert gen.progress == 100

        songs = list(
            s.execute(Song.__table__.select().where(Song.generation_id == gen_id))
        )
        assert len(songs) == 2

        ledger_types = [
            r._mapping["type"]
            for r in s.execute(
                CreditLedger.__table__.select().where(CreditLedger.user_id == user_id)
            )
        ]
        assert "hold" in ledger_types
        assert "charge" in ledger_types

    events = [c.args[1].get("event") for c in pub.call_args_list]
    assert "completed" in events
