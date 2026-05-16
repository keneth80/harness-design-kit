"""사용자별 FTS5 세션 검색.

격리: 사용자마다 별도 SQLite 파일 (data/users/<user_id>/sessions.db).
      cross-user 검색은 구조적으로 불가능 (DB가 다름).

스키마: FTS5 가상 테이블 messages(session_id, role, content, ts UNINDEXED, agent_id UNINDEXED).
        tokenize='unicode61' — 한국어 토큰 분리 호환.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from src.core.logger import get_logger
from src.self_improvement.user_registry import (
    UserRegistry,
    get_registry,
)

_log = get_logger("self_improvement.search")


_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages USING fts5(
    session_id,
    role,
    content,
    ts UNINDEXED,
    agent_id UNINDEXED,
    tokenize='unicode61 remove_diacritics 2'
);
"""


def _escape_fts(query: str) -> str:
    """FTS5 query escape — 사용자 입력을 안전한 phrase로 변환.

    공백 분리 후 각 토큰을 "..." 로 감싸 OR 조합.
    빈 입력은 빈 문자열.
    """
    tokens = [t for t in query.replace('"', "").split() if t.strip()]
    if not tokens:
        return ""
    quoted = [f'"{t}"' for t in tokens]
    return " OR ".join(quoted)


class SessionSearch:
    def __init__(
        self,
        data_dir: Path,
        registry: UserRegistry | None = None,
    ) -> None:
        self._data_dir = data_dir
        self._registry = registry or get_registry()
        self._conns: dict[str, sqlite3.Connection] = {}
        self._lock = threading.RLock()

    # ─── 연결 관리 ────────────────────────────────────
    def _db(self, user_id: str) -> sqlite3.Connection:
        # 검증 (path traversal / 미등록 차단)
        self._registry.get(user_id)
        with self._lock:
            if user_id not in self._conns:
                d = self._data_dir / "users" / user_id
                d.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(
                    str(d / "sessions.db"),
                    check_same_thread=False,
                )
                conn.executescript(_SCHEMA)
                conn.commit()
                self._conns[user_id] = conn
            return self._conns[user_id]

    def close_all(self) -> None:
        with self._lock:
            for c in self._conns.values():
                try:
                    c.close()
                except Exception:
                    pass
            self._conns.clear()

    # ─── 저장 ─────────────────────────────────────────
    def save_message(
        self,
        user_id: str,
        *,
        session_id: str,
        role: str,
        content: str,
        agent_id: str | None = None,
        ts: str | None = None,
    ) -> None:
        if not content:
            return
        db = self._db(user_id)
        ts = ts or datetime.now(timezone.utc).isoformat()
        with self._lock:
            db.execute(
                "INSERT INTO messages (session_id, role, content, ts, agent_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, ts, agent_id or ""),
            )
            db.commit()

    # ─── 검색 ─────────────────────────────────────────
    def search(
        self,
        user_id: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[dict]:
        q = _escape_fts(query)
        if not q:
            return []
        db = self._db(user_id)
        with self._lock:
            try:
                cur = db.execute(
                    "SELECT session_id, role, content, ts, agent_id, "
                    "snippet(messages, 2, '«', '»', '…', 12) AS snip "
                    "FROM messages WHERE messages MATCH ? "
                    "ORDER BY rank LIMIT ?",
                    (q, top_k),
                )
                rows = cur.fetchall()
            except sqlite3.OperationalError as e:
                _log.warning(f"fts search error uid={user_id} q={q!r}: {e}")
                return []
        return [
            {
                "session_id": r[0],
                "role": r[1],
                "content": r[2],
                "ts": r[3],
                "agent_id": r[4],
                "snippet": r[5],
            }
            for r in rows
        ]

    def count(self, user_id: str) -> int:
        db = self._db(user_id)
        with self._lock:
            return db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]


def _smoke() -> None:
    """수동 실행: python -m src.self_improvement.session_search"""
    import tempfile

    tmp = Path(tempfile.mkdtemp())
    from src.self_improvement.user_registry import UserRegistry

    reg = UserRegistry(tmp / "users" / "_registry.json")
    reg.add_member(telegram_id="121095851", alias="wife")

    s = SessionSearch(tmp, registry=reg)
    s.save_message(
        "wife", session_id="s1", role="user", content="비빔밥 레시피 알려줘"
    )
    s.save_message(
        "wife", session_id="s1", role="assistant", content="고추장과 야채로 비빔"
    )
    print("hits:", s.search("wife", "비빔밥"))


if __name__ == "__main__":
    _smoke()
