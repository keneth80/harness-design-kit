"""Reflection 엔진 단위 + 격리 테스트.

LM Studio 실제 호출 없이 Mock client로 검증한다.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from src.self_improvement.memory_store import MemoryStore
from src.self_improvement.reflection import (
    ReflectionEngine,
    _format_conversation,
    _parse_reflection,
)
from src.self_improvement.user_registry import UserRegistry


class FakeClient:
    """LMStudioClient stub. 호출별로 응답 정의."""

    def __init__(self, response: str | dict) -> None:
        if isinstance(response, dict):
            response = json.dumps(response, ensure_ascii=False)
        self._response = response
        self.calls: list[list[dict]] = []
        self.delay = 0.0

    async def chat(self, messages, **kwargs):
        self.calls.append(list(messages))
        if self.delay:
            await asyncio.sleep(self.delay)
        return self._response


@pytest.fixture
def env(monkeypatch):
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setenv("DATA_DIR", str(tmp))
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "109494677")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tt")
    from src.core import config as cfg

    cfg.get_settings.cache_clear()
    reg = UserRegistry(tmp / "users" / "_registry.json")
    reg.add_member(telegram_id="121095851", alias="wife")
    reg.add_member(telegram_id="345678901", alias="son1", is_minor=True)
    mem = MemoryStore(tmp, registry=reg)
    return tmp, reg, mem


# ─── 파서 ─────────────────────────────────────────
def test_parse_clean_json():
    raw = '{"new_memories":[{"section":"사실","fact":"비빔밥 좋아함"}]}'
    obj = _parse_reflection(raw)
    assert obj["new_memories"][0]["fact"] == "비빔밥 좋아함"


def test_parse_with_codefence():
    raw = '```json\n{"new_memories":[]}\n```'
    obj = _parse_reflection(raw)
    assert obj == {"new_memories": []}


def test_parse_with_prefix():
    raw = '결과:\n{"new_memories":[]}'
    obj = _parse_reflection(raw)
    assert obj == {"new_memories": []}


def test_parse_invalid_returns_empty():
    assert _parse_reflection("이상한 응답") == {}
    assert _parse_reflection("") == {}


def test_format_conversation_drops_system():
    msgs = [
        {"role": "system", "content": "시스템 프롬프트"},
        {"role": "user", "content": "안녕"},
        {"role": "assistant", "content": "안녕하세요"},
    ]
    text = _format_conversation(msgs)
    assert "시스템 프롬프트" not in text
    assert "[user] 안녕" in text
    assert "[assistant] 안녕하세요" in text


def test_format_conversation_truncates(monkeypatch):
    from src.self_improvement import reflection as ref

    monkeypatch.setattr(ref, "_MAX_CONV_CHARS", 50)
    msgs = [{"role": "user", "content": "x" * 200}]
    text = ref._format_conversation(msgs)
    assert len(text) <= 50


# ─── 자성 결과가 메모리에 반영 ─────────────────────
@pytest.mark.asyncio
async def test_reflection_writes_memory_and_profile(env):
    _, reg, mem = env
    client = FakeClient(
        {
            "new_memories": [{"section": "사실", "fact": "비빔밥 선호"}],
            "user_observations": [
                {"section": "선호", "obs": "한식 위주 식사"}
            ],
            "skill_worthy": False,
        }
    )
    engine = ReflectionEngine(mem, client, registry=reg, reflect_every=2)
    engine._counters["wife"] = 2  # 임계점 도달
    conv = [
        {"role": "user", "content": "오늘 점심 비빔밥 어때?"},
        {"role": "assistant", "content": "비빔밥 좋은 선택입니다."},
    ]
    result = await engine.maybe_reflect("wife", conv)
    assert result is not None
    assert "비빔밥 선호" in mem.get_memory("wife")
    assert "한식 위주 식사" in mem.get_user_profile("wife")


# ─── N턴 카운터 ────────────────────────────────────
@pytest.mark.asyncio
async def test_reflection_skips_until_threshold(env):
    _, reg, mem = env
    client = FakeClient({"new_memories": []})
    engine = ReflectionEngine(mem, client, registry=reg, reflect_every=3)
    for _ in range(2):
        engine.increment("wife")
        r = await engine.maybe_reflect("wife", [{"role": "user", "content": "x"}])
        assert r is None
    engine.increment("wife")  # 카운터 3
    r = await engine.maybe_reflect("wife", [{"role": "user", "content": "x"}])
    assert r is not None
    # 호출 후 카운터 리셋
    assert engine.turn_count("wife") == 0


# ─── 다른 사용자 정보 누수 차단 ──────────────────────
@pytest.mark.asyncio
async def test_reflection_drops_facts_mentioning_other_user(env):
    _, reg, mem = env
    client = FakeClient(
        {
            "new_memories": [
                {"section": "사실", "fact": "wife가 비빔밥 좋아함"},  # 다른 사용자 언급
                {"section": "사실", "fact": "내가 영화 좋아함"},  # OK
            ],
            "user_observations": [],
            "skill_worthy": False,
        }
    )
    engine = ReflectionEngine(mem, client, registry=reg, reflect_every=1)
    engine._counters["tg_109494677"] = 1
    await engine.maybe_reflect(
        "tg_109494677", [{"role": "user", "content": "x"}], force=True
    )
    text = mem.get_memory("tg_109494677")
    assert "wife가 비빔밥" not in text
    assert "영화 좋아함" in text


# ─── 미성년자 민감 관찰 차단 (memory_store 자동) ─────
@pytest.mark.asyncio
async def test_reflection_minor_filters_sensitive(env):
    _, reg, mem = env
    client = FakeClient(
        {
            "new_memories": [{"section": "사실", "fact": "수학 좋아함"}],
            "user_observations": [
                {"section": "컨텍스트", "obs": "최근 가족 갈등 노출"},  # 민감 → 거부
                {"section": "관심사", "obs": "공룡 책 좋아함"},  # OK
            ],
            "skill_worthy": False,
        }
    )
    engine = ReflectionEngine(mem, client, registry=reg, reflect_every=1)
    await engine.maybe_reflect(
        "son1", [{"role": "user", "content": "x"}], force=True
    )
    profile = mem.get_user_profile("son1")
    assert "가족 갈등" not in profile
    assert "공룡 책" in profile


# ─── 사용자별 락이 다른 사용자 블로킹 안 함 ─────────
@pytest.mark.asyncio
async def test_per_user_locks_isolate(env):
    _, reg, mem = env
    client = FakeClient({"new_memories": [], "user_observations": []})
    client.delay = 0.1  # 호출에 100ms

    engine = ReflectionEngine(mem, client, registry=reg, reflect_every=1)
    engine._counters["tg_109494677"] = 1
    engine._counters["wife"] = 1

    import time

    start = time.time()
    await asyncio.gather(
        engine.maybe_reflect(
            "tg_109494677", [{"role": "user", "content": "a"}], force=True
        ),
        engine.maybe_reflect(
            "wife", [{"role": "user", "content": "b"}], force=True
        ),
    )
    elapsed = time.time() - start
    # 동시 실행이라 0.1~0.15초 사이여야 함 (직렬이면 0.2초 이상)
    assert elapsed < 0.18, f"locks blocked across users: {elapsed:.3f}s"


# ─── 글로벌 세마포어가 LLM 동시 호출 제한 ────────────
@pytest.mark.asyncio
async def test_global_semaphore_throttles_llm(env):
    _, reg, mem = env
    reg.add_member(telegram_id="222", alias="member3")
    reg.add_member(telegram_id="333", alias="member4")
    client = FakeClient({"new_memories": []})
    client.delay = 0.15
    engine = ReflectionEngine(
        mem, client, registry=reg, reflect_every=1, global_concurrency=2
    )
    import time

    start = time.time()
    await asyncio.gather(
        engine.maybe_reflect(
            "tg_109494677", [{"role": "user", "content": "a"}], force=True
        ),
        engine.maybe_reflect(
            "wife", [{"role": "user", "content": "b"}], force=True
        ),
        engine.maybe_reflect(
            "member3", [{"role": "user", "content": "c"}], force=True
        ),
        engine.maybe_reflect(
            "member4", [{"role": "user", "content": "d"}], force=True
        ),
    )
    elapsed = time.time() - start
    # 4건이 동시성 2로 → 2배치 → 0.3초 이상이어야
    assert elapsed >= 0.25, f"semaphore did not throttle: {elapsed:.3f}s"


# ─── 파싱 실패 → 안전 폴백 ─────────────────────────
@pytest.mark.asyncio
async def test_reflection_parse_failure_returns_empty(env):
    _, reg, mem = env
    client = FakeClient("완전히 깨진 응답")
    engine = ReflectionEngine(mem, client, registry=reg, reflect_every=1)
    r = await engine.maybe_reflect(
        "wife", [{"role": "user", "content": "x"}], force=True
    )
    assert r is not None
    assert r.error == "parse"
    # 메모리는 변경되지 않아야 함
    assert "(아직 비어 있음)" in mem.get_memory("wife")
