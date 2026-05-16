"""공유 메모리 + PII 필터 + 감사 로그 격리 테스트."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.self_improvement import pii_filter
from src.self_improvement.context_loader import ContextLoader
from src.self_improvement.memory_store import MemoryStore
from src.self_improvement.shared_memory import SharedMemoryStore
from src.self_improvement.user_registry import (
    UnauthorizedError,
    UserRegistry,
)


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
    mem = MemoryStore(tmp, registry=registry)
    shared = SharedMemoryStore(tmp, registry=registry)
    loader = ContextLoader(mem, registry=registry)
    loader.attach_shared_memory(shared)
    return tmp, registry, mem, shared, loader


# ─── PII 필터 ─────────────────────────────────────
def test_pii_redacts_openai_key():
    text = "API key is sk-abc1234567890abcdefghij"
    out = pii_filter.clean(text, level="shared")
    assert "sk-abc" not in out
    assert "<API_KEY_REDACTED>" in out


def test_pii_redacts_anthropic_key():
    text = "sk-ant-abc-1234567890abcdefghij and more"
    out = pii_filter.clean(text, level="shared")
    assert "sk-ant" not in out


def test_pii_redacts_telegram_token():
    text = "token: 8705782822:ABCdefGHIjklMNOpqrSTUvwxYZ0123456789"
    out = pii_filter.clean(text, level="shared")
    assert "8705782822:" not in out


def test_pii_redacts_rrn():
    text = "주민번호: 900101-1234567 입니다"
    out = pii_filter.clean(text, level="shared")
    assert "900101-1234567" not in out


def test_pii_levels_shared_keeps_email():
    text = "연락처는 alice@example.com 010-1234-5678 입니다"
    out_shared = pii_filter.clean(text, level="shared")
    out_skill = pii_filter.clean(text, level="skill")
    assert "alice@example.com" in out_shared  # shared 레벨은 이메일 유지
    assert "010-1234-5678" in out_shared
    assert "alice@example.com" not in out_skill  # skill 레벨에서만 마스킹
    assert "010-1234-5678" not in out_skill


# ─── admin-only 쓰기 ─────────────────────────────
def test_admin_can_share(env):
    _, _, _, shared, _ = env
    shared.append("tg_109494677", "집 Wi-Fi 비밀번호는 secret-pw")
    content = shared.read("tg_109494677")
    assert "Wi-Fi" in content


def test_non_admin_cannot_share(env):
    _, _, _, shared, _ = env
    with pytest.raises(UnauthorizedError):
        shared.append("wife", "이건 쓰지 못함")


def test_minor_cannot_share(env):
    _, _, _, shared, _ = env
    with pytest.raises(UnauthorizedError):
        shared.append("son1", "쓰지 못함")


def test_unauthorized_share_attempt_audited(env):
    _, _, _, shared, _ = env
    try:
        shared.append("wife", "secret")
    except UnauthorizedError:
        pass
    audit = shared.audit_tail()
    assert any(
        e["user_id"] == "wife" and e["action"] == "DENIED_WRITE" for e in audit
    )


# ─── 읽기 권한 ─────────────────────────────────────
def test_admin_can_read(env):
    _, _, _, shared, _ = env
    shared.append("tg_109494677", "공유 사실 1")
    assert "공유 사실 1" in shared.read("tg_109494677")


def test_adult_member_can_read(env):
    _, _, _, shared, _ = env
    shared.append("tg_109494677", "가족 일정")
    assert "가족 일정" in shared.read("wife")


def test_minor_gets_empty_shared(env):
    _, _, _, shared, _ = env
    shared.append("tg_109494677", "어른 정보")
    assert shared.read("son1") == ""


# ─── 컨텍스트에 공유 메모리 주입 ────────────────────
def test_context_includes_shared_for_adult(env):
    _, _, _, shared, loader = env
    shared.append("tg_109494677", "Wi-Fi 비번")
    ctx = loader.build_system_prompt(
        user_id="wife", base_prompt="JARVIS", user_message="안녕"
    )
    assert "Wi-Fi 비번" in ctx


def test_context_excludes_shared_for_minor(env):
    _, _, _, shared, loader = env
    shared.append("tg_109494677", "어른 정보")
    ctx = loader.build_system_prompt(
        user_id="son1", base_prompt="JARVIS", user_message="안녕"
    )
    assert "어른 정보" not in ctx


# ─── 쓰기 시 PII 자동 마스킹 ─────────────────────
def test_share_redacts_api_key(env):
    _, _, _, shared, _ = env
    shared.append(
        "tg_109494677",
        "OpenAI 키: sk-abcdef1234567890abcdefghij 입니다",
    )
    content = shared.read("tg_109494677")
    assert "sk-abcdef" not in content
    assert "<API_KEY_REDACTED>" in content


# ─── /forget admin-only ─────────────────────────────
def test_forget_admin_only(env):
    _, _, _, shared, _ = env
    shared.append("tg_109494677", "예전 정보")
    with pytest.raises(UnauthorizedError):
        shared.forget("wife", "예전")
    removed = shared.forget("tg_109494677", "예전")
    assert removed >= 1


# ─── 감사 로그 ──────────────────────────────────────
def test_audit_tail_records_writes(env):
    _, _, _, shared, _ = env
    shared.append("tg_109494677", "A")
    shared.append("tg_109494677", "B")
    audit = shared.audit_tail()
    write_actions = [e for e in audit if e["action"] == "WRITE"]
    assert len(write_actions) >= 2
