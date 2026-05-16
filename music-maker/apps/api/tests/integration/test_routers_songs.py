"""Integration: POST /api/v1/songs (202 + holds credit + enqueues)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.models.credit_ledger import CreditLedger
from app.models.generation import Generation
from sqlalchemy import select


@pytest.mark.asyncio
async def test_create_generation_returns_202_and_holds_credit(
    client, current_user, session_factory
):
    payload = {
        "mode": "song",
        "prompt": {"text": "비 오는 도쿄 새벽, 잔잔한 피아노", "length_s": 60},
        "lyrics_mode": "none",
        "model": "mureka-7",
    }
    with patch("app.routers.songs._enqueue") as enqueue:
        resp = await client.post("/api/v1/songs", json=payload)
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert "generation_id" in body
    assert body["status"] == "queued"
    assert body["credit_cost"] == 1
    assert body["credits_remaining"] == 9  # 10 seed - 1 hold
    assert body["subscribe_url"].startswith("/api/v1/songs/")
    enqueue.assert_called_once()

    # DB side effects
    async with session_factory() as s:
        gen_id = uuid.UUID(body["generation_id"])
        gen = await s.get(Generation, gen_id)
        assert gen is not None
        assert gen.user_id == current_user.id
        assert gen.status == "queued"
        ledger = (
            await s.execute(
                select(CreditLedger).where(CreditLedger.generation_id == gen_id)
            )
        ).scalars().all()
        assert any(l.type == "hold" and l.amount == -1 for l in ledger)


@pytest.mark.asyncio
async def test_get_generation_returns_403_when_owner_mismatch(client, session_factory):
    """Generation owned by another user → 403."""
    from app.models.user import User

    other_id = uuid.uuid4()
    async with session_factory() as s:
        other = User(id=other_id, email=f"other-{other_id.hex[:6]}@x.y", plan="free")
        gen = Generation(
            id=uuid.uuid4(),
            user_id=other_id,
            mode="song",
            prompt={"text": "x"},
            model="auto",
            credit_cost=1,
            status="queued",
        )
        s.add(other)
        s.add(gen)
        await s.commit()
        gen_id = gen.id

    resp = await client.get(f"/api/v1/songs/{gen_id}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_generation_404_when_unknown(client):
    resp = await client.get(f"/api/v1/songs/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_account_credits_endpoint(client):
    resp = await client.get("/api/v1/account/credits")
    assert resp.status_code == 200
    data = resp.json()
    assert data["credits"] == 10
    assert data["plan"] == "pro"


@pytest.mark.asyncio
async def test_library_lists_user_songs(client, current_user, session_factory):
    from app.models.song import Song

    async with session_factory() as s:
        gen = Generation(
            id=uuid.uuid4(),
            user_id=current_user.id,
            mode="song",
            prompt={"text": "x"},
            model="auto",
            credit_cost=1,
            status="completed",
        )
        s.add(gen)
        await s.flush()
        s.add(
            Song(
                id=uuid.uuid4(),
                generation_id=gen.id,
                variant="A",
                storage_key="songs/x/A.mp3",
                mp3_url="http://cdn/x/A.mp3",
            )
        )
        await s.commit()

    resp = await client.get("/api/v1/library?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["variant"] == "A"
