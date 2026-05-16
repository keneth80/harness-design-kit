"""ContextBuilder 단위 테스트."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.memory.long_term import LongTermMemory
from src.memory.short_term import ContextBuilder, SYSTEM_PROMPT_DEFAULT


@pytest.fixture
async def memory() -> LongTermMemory:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    mem = LongTermMemory(db_path=Path(tmp.name))
    await mem.init()
    return mem


@pytest.mark.asyncio
async def test_build_includes_system_and_user(memory: LongTermMemory) -> None:
    sid = await memory.start_session("u")
    builder = ContextBuilder(memory, window_turns=5)
    msgs = await builder.build(session_id=sid, user_message="hi there")
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == SYSTEM_PROMPT_DEFAULT
    assert msgs[-1] == {"role": "user", "content": "hi there"}


@pytest.mark.asyncio
async def test_build_injects_prior_summary(memory: LongTermMemory) -> None:
    sid = await memory.start_session("u")
    builder = ContextBuilder(memory, window_turns=5)
    msgs = await builder.build(
        session_id=sid, user_message="q", prior_summary="이전에 비빔밥 얘기."
    )
    summaries = [m for m in msgs if "[직전 세션 요약]" in m["content"]]
    assert len(summaries) == 1
    assert "비빔밥" in summaries[0]["content"]


@pytest.mark.asyncio
async def test_build_includes_recent_window(memory: LongTermMemory) -> None:
    sid = await memory.start_session("u")
    for i in range(6):
        await memory.add_message(
            session_id=sid, user_id="u", role="user", content=f"q{i}"
        )
        await memory.add_message(
            session_id=sid, user_id="u", role="assistant", content=f"a{i}"
        )
    builder = ContextBuilder(memory, window_turns=2)
    msgs = await builder.build(session_id=sid, user_message="new")
    # 2턴 = 4메시지 + system + user new = 6
    user_assistant = [m for m in msgs if m["role"] in ("user", "assistant")]
    # 마지막 user 'new' 포함, 그 앞이 a5, q5, a4, q4
    assert user_assistant[-1]["content"] == "new"
    assert user_assistant[-2]["content"] == "a5"
    assert user_assistant[-5]["content"] == "q4"


@pytest.mark.asyncio
async def test_build_with_extra_context(memory: LongTermMemory) -> None:
    sid = await memory.start_session("u")
    builder = ContextBuilder(memory)
    msgs = await builder.build(
        session_id=sid, user_message="q", extra_context="문서 일부 발췌"
    )
    assert any("[참고 문서]" in m["content"] for m in msgs)
