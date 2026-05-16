"""사용자별 MEMORY/USER 격리 + 미성년자 필터 + 컨텍스트 조립 테스트."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.self_improvement.memory_store import MemoryStore
from src.self_improvement.context_loader import ContextLoader
from src.self_improvement.user_registry import UnauthorizedError, UserRegistry


@pytest.fixture
def env(monkeypatch):
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setenv("DATA_DIR", str(tmp))
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "109494677")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tt")
    from src.core import config as cfg

    cfg.get_settings.cache_clear()
    registry = UserRegistry(tmp / "users" / "_registry.json")
    registry.add_member(telegram_id="121095851", alias="wife", display_name="사모님")
    registry.add_member(
        telegram_id="345678901", alias="son1", display_name="큰아들", is_minor=True
    )
    store = MemoryStore(tmp, registry=registry)
    loader = ContextLoader(store, registry=registry)
    return tmp, registry, store, loader


# ─── 격리 ───────────────────────────────────────────
def test_cross_user_memory_isolation(env):
    _, _, store, _ = env
    store.append_memory("tg_109494677", "사실", "kenneth 비밀 정보")
    store.append_memory("wife", "사실", "wife의 다른 사실")
    # kenneth 파일에 wife 내용 없어야 함
    k = store.get_memory("tg_109494677")
    w = store.get_memory("wife")
    assert "kenneth 비밀 정보" in k and "wife의 다른 사실" not in k
    assert "wife의 다른 사실" in w and "kenneth 비밀 정보" not in w


def test_unknown_user_raises(env):
    _, _, store, _ = env
    with pytest.raises(UnauthorizedError):
        store.append_memory("unknown_uid", "사실", "x")


def test_path_traversal_blocked_at_memory_layer(env):
    _, _, store, _ = env
    with pytest.raises(UnauthorizedError):
        store.append_memory("../../etc/passwd", "사실", "x")


# ─── 컨텍스트 조립 ──────────────────────────────────
def test_context_includes_only_own_memory(env):
    _, _, store, loader = env
    store.append_memory("tg_109494677", "사실", "kenneth: 영화 좋아함")
    store.append_memory("wife", "사실", "wife: 라떼 선호")

    ctx_k = loader.build_system_prompt(
        user_id="tg_109494677", base_prompt="당신은 JARVIS", user_message="안녕"
    )
    ctx_w = loader.build_system_prompt(
        user_id="wife", base_prompt="당신은 JARVIS", user_message="안녕"
    )
    assert "kenneth: 영화 좋아함" in ctx_k
    assert "wife: 라떼 선호" not in ctx_k
    assert "wife: 라떼 선호" in ctx_w
    assert "kenneth: 영화 좋아함" not in ctx_w


def test_context_unknown_user_raises(env):
    _, _, _, loader = env
    with pytest.raises(UnauthorizedError):
        loader.build_system_prompt(
            user_id="nobody", base_prompt="x", user_message="y"
        )


# ─── 미성년자 보호 ───────────────────────────────────
def test_minor_sensitive_observation_blocked(env):
    _, _, store, _ = env
    ok = store.update_user_profile("son1", "관심사", "수학과 게임을 좋아함")
    assert ok is True
    # 민감 키워드 포함 → 거절
    rejected = store.update_user_profile("son1", "컨텍스트", "최근 가족 갈등에 노출")
    assert rejected is False
    profile = store.get_user_profile("son1")
    assert "가족 갈등" not in profile
    assert "수학과 게임" in profile


def test_adult_sensitive_observation_allowed(env):
    _, _, store, _ = env
    # 성인은 같은 단어가 들어가도 허용
    ok = store.update_user_profile("wife", "컨텍스트", "최근 직장 갈등 호소")
    assert ok is True
    assert "직장 갈등" in store.get_user_profile("wife")


# ─── forget ─────────────────────────────────────────
def test_forget_removes_matching_lines(env):
    _, _, store, _ = env
    store.append_memory("wife", "사실", "라떼 선호")
    store.append_memory("wife", "사실", "초콜릿 알러지")
    removed = store.forget("wife", "라떼")
    assert removed == 1
    mem = store.get_memory("wife")
    assert "라떼 선호" not in mem
    assert "초콜릿 알러지" in mem


# ─── 원자적 쓰기 (tmp 잔여물 없음) ───────────────────
def test_no_tmp_residue_after_writes(env):
    tmp, _, store, _ = env
    for i in range(20):
        store.append_memory("wife", "사실", f"item-{i}")
    user_dir = tmp / "users" / "wife"
    residue = list(user_dir.glob("*.tmp.*"))
    assert residue == []
