"""SQLite 기반 대화 영속화. 비동기 CRUD."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from src.core.config import get_settings
from src.core.logger import get_logger

_log = get_logger("memory.long_term")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    ts TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS allowed_users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    added_by INTEGER NOT NULL,
    added_at TEXT NOT NULL,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, ts);
CREATE INDEX IF NOT EXISTS idx_session_user ON sessions(user_id, last_active_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Message:
    id: str
    user_id: str
    session_id: str
    role: str
    content: str
    ts: str
    metadata: dict[str, Any]


@dataclass
class Session:
    id: str
    user_id: str
    started_at: str
    last_active_at: str
    summary: str | None


class LongTermMemory:
    def __init__(self, db_path: Path | None = None) -> None:
        settings = get_settings()
        self._db_path = db_path or settings.data_dir / "conversations.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()
        _log.info(f"long_term ready @ {self._db_path}")

    async def start_session(self, user_id: str) -> str:
        sid = uuid.uuid4().hex
        now = _now()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO sessions (id, user_id, started_at, last_active_at) VALUES (?, ?, ?, ?)",
                (sid, user_id, now, now),
            )
            await db.commit()
        _log.info(f"session start user={user_id} sid={sid}")
        return sid

    async def add_message(
        self,
        *,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        mid = uuid.uuid4().hex
        now = _now()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO conversations (id, user_id, session_id, role, content, ts, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mid, user_id, session_id, role, content, now, meta_json),
            )
            await db.execute(
                "UPDATE sessions SET last_active_at=? WHERE id=?", (now, session_id)
            )
            await db.commit()
        return mid

    async def get_session_messages(
        self, session_id: str, limit: int | None = None
    ) -> list[Message]:
        sql = (
            "SELECT id, user_id, session_id, role, content, ts, metadata_json "
            "FROM conversations WHERE session_id=? ORDER BY ts ASC"
        )
        params: tuple[Any, ...] = (session_id,)
        if limit is not None:
            sql = (
                "SELECT * FROM (SELECT id, user_id, session_id, role, content, ts, metadata_json "
                "FROM conversations WHERE session_id=? ORDER BY ts DESC LIMIT ?) ORDER BY ts ASC"
            )
            params = (session_id, limit)
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()
        return [
            Message(
                id=r[0],
                user_id=r[1],
                session_id=r[2],
                role=r[3],
                content=r[4],
                ts=r[5],
                metadata=json.loads(r[6] or "{}"),
            )
            for r in rows
        ]

    async def latest_session(self, user_id: str) -> Session | None:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT id, user_id, started_at, last_active_at, summary "
                "FROM sessions WHERE user_id=? ORDER BY last_active_at DESC LIMIT 1",
                (user_id,),
            ) as cur:
                row = await cur.fetchone()
        if row is None:
            return None
        return Session(*row)

    async def save_summary(self, session_id: str, summary: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE sessions SET summary=? WHERE id=?", (summary, session_id)
            )
            await db.commit()
        _log.info(f"summary saved sid={session_id} len={len(summary)}")

    # ─── allowed_users ──────────────────────────────────────────────
    async def add_allowed_user(
        self,
        user_id: int,
        *,
        added_by: int,
        username: str | None = None,
        note: str | None = None,
    ) -> bool:
        """이미 존재하면 False, 새로 추가하면 True."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT user_id FROM allowed_users WHERE user_id=?", (user_id,)
            ) as cur:
                if await cur.fetchone():
                    return False
            await db.execute(
                "INSERT INTO allowed_users (user_id, username, added_by, added_at, note) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, username, added_by, _now(), note),
            )
            await db.commit()
        _log.info(f"allowed user added uid={user_id} by={added_by}")
        return True

    async def remove_allowed_user(self, user_id: int) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                "DELETE FROM allowed_users WHERE user_id=?", (user_id,)
            )
            await db.commit()
            removed = cur.rowcount > 0
        _log.info(f"allowed user removed uid={user_id} removed={removed}")
        return removed

    async def list_allowed_users(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT user_id, username, added_by, added_at, note FROM allowed_users ORDER BY added_at"
            ) as cur:
                rows = await cur.fetchall()
        return [
            {
                "user_id": r[0],
                "username": r[1],
                "added_by": r[2],
                "added_at": r[3],
                "note": r[4],
            }
            for r in rows
        ]

    async def is_user_allowed_db(self, user_id: int) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT 1 FROM allowed_users WHERE user_id=?", (user_id,)
            ) as cur:
                return await cur.fetchone() is not None

    async def end_session(self, session_id: str, summary: str | None = None) -> None:
        if summary:
            await self.save_summary(session_id, summary)
        _log.info(f"session end sid={session_id}")

    async def generate_summary(
        self,
        session_id: str,
        llm_client,
        *,
        min_messages: int = 4,
    ) -> str | None:
        """세션 메시지를 LLM으로 요약 후 sessions.summary에 저장. 메시지가 부족하면 None."""
        msgs = await self.get_session_messages(session_id)
        msgs = [m for m in msgs if m.role in ("user", "assistant")]
        if len(msgs) < min_messages:
            return None
        transcript = "\n".join(f"[{m.role}] {m.content}" for m in msgs)
        prompt = [
            {
                "role": "system",
                "content": (
                    "다음 대화를 한국어로 3~5문장으로 요약하라. "
                    "사용자의 관심사·결정·미해결 주제를 위주로, "
                    "다음 세션에서 컨텍스트로 사용할 수 있도록 명사 중심으로."
                ),
            },
            {"role": "user", "content": transcript},
        ]
        try:
            summary = await llm_client.chat(prompt, temperature=0.2)
        except Exception as e:
            _log.warning(f"summary generation failed sid={session_id}: {e}")
            return None
        summary = (summary or "").strip()
        if not summary:
            return None
        await self.save_summary(session_id, summary)
        return summary


async def _smoke() -> None:
    mem = LongTermMemory()
    await mem.init()
    sid = await mem.start_session("test-user")
    await mem.add_message(session_id=sid, user_id="test-user", role="user", content="hi")
    await mem.add_message(
        session_id=sid, user_id="test-user", role="assistant", content="hello"
    )
    msgs = await mem.get_session_messages(sid)
    print(f"messages: {len(msgs)}")
    for m in msgs:
        print(f"  [{m.role}] {m.content}")
    await mem.save_summary(sid, "test session")
    latest = await mem.latest_session("test-user")
    print(f"latest summary: {latest.summary if latest else None}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(_smoke())
