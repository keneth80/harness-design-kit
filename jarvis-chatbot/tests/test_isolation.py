"""격리/권한 보안 테스트.

이 파일의 모든 테스트는 cross-user 누수, 권한 우회, path traversal을
차단하는지 검증한다. 절대 skip되어선 안 된다.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from src.self_improvement import permissions
from src.self_improvement.user_registry import (
    UnauthorizedError,
    User,
    UserRegistry,
)


@pytest.fixture
def tmp_registry(monkeypatch) -> UserRegistry:
    # data_dir 분리
    tmp = Path(tempfile.mkdtemp())
    (tmp / "users").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", str(tmp))
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "109494677")  # admin
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    # config 캐시 무효화
    from src.core import config as cfg

    cfg.get_settings.cache_clear()
    return UserRegistry(tmp / "users" / "_registry.json")


# ─── path traversal 차단 ─────────────────────────────
@pytest.mark.parametrize(
    "bad",
    [
        "../../../etc/passwd",
        "..",
        "a/b",
        "a\\b",
        "a..b",
        "",
        None,
        "1abc",  # 숫자 시작 금지
        "kenneth!",  # 특수문자 금지
        "x" * 80,  # 너무 김
    ],
)
def test_get_rejects_bad_user_id(tmp_registry, bad):
    with pytest.raises(UnauthorizedError):
        tmp_registry.get(bad)


# ─── admin 자동 등록 ──────────────────────────────────
def test_admin_auto_registered_from_env(tmp_registry):
    user = tmp_registry.by_telegram_id("109494677")
    assert user is not None
    assert user.role == "admin"
    assert user.user_id == "tg_109494677"


def test_non_registered_telegram_returns_none(tmp_registry):
    assert tmp_registry.by_telegram_id("999999999") is None


# ─── 멤버 추가/제거 ───────────────────────────────────
def test_add_member_and_lookup(tmp_registry):
    user = tmp_registry.add_member(
        telegram_id="121095851", display_name="친구", note="ex-coworker"
    )
    assert user.user_id == "tg_121095851"
    assert user.role == "user"
    assert tmp_registry.by_telegram_id("121095851").user_id == "tg_121095851"


def test_add_member_with_alias(tmp_registry):
    user = tmp_registry.add_member(
        telegram_id="121095851", alias="wife", display_name="사모님"
    )
    assert user.user_id == "wife"
    assert tmp_registry.by_telegram_id("121095851").user_id == "wife"


def test_cannot_add_admin_as_member(tmp_registry):
    with pytest.raises(UnauthorizedError):
        tmp_registry.add_member(telegram_id="109494677", alias="me")


def test_cannot_add_duplicate_telegram(tmp_registry):
    tmp_registry.add_member(telegram_id="121095851")
    with pytest.raises(UnauthorizedError):
        tmp_registry.add_member(telegram_id="121095851", alias="other")


def test_remove_member_protects_admin(tmp_registry):
    # admin은 .env로 관리. registry에서 제거 시도해도 False.
    assert tmp_registry.remove_member("tg_109494677") is False


def test_remove_unregistered_returns_false(tmp_registry):
    assert tmp_registry.remove_member("unknown_user") is False


# ─── 별칭 rename ─────────────────────────────────────
def test_set_alias(tmp_registry):
    tmp_registry.add_member(telegram_id="121095851")
    renamed = tmp_registry.set_alias("tg_121095851", "wife")
    assert renamed.user_id == "wife"
    assert tmp_registry.by_telegram_id("121095851").user_id == "wife"
    with pytest.raises(UnauthorizedError):
        tmp_registry.get("tg_121095851")  # 옛 ID는 사라짐


# ─── 권한 체크 ────────────────────────────────────────
def test_require_admin_passes_for_admin(tmp_registry, monkeypatch):
    monkeypatch.setattr(permissions, "get_registry", lambda: tmp_registry)
    permissions.require_admin("tg_109494677")


def test_require_admin_blocks_member(tmp_registry, monkeypatch):
    monkeypatch.setattr(permissions, "get_registry", lambda: tmp_registry)
    tmp_registry.add_member(telegram_id="121095851", alias="friend")
    with pytest.raises(UnauthorizedError):
        permissions.require_admin("friend")


def test_require_admin_blocks_unknown(tmp_registry, monkeypatch):
    monkeypatch.setattr(permissions, "get_registry", lambda: tmp_registry)
    with pytest.raises(UnauthorizedError):
        permissions.require_admin("nobody")


def test_require_adult_blocks_minor(tmp_registry, monkeypatch):
    monkeypatch.setattr(permissions, "get_registry", lambda: tmp_registry)
    tmp_registry.add_member(telegram_id="345678901", alias="son1", is_minor=True)
    with pytest.raises(UnauthorizedError):
        permissions.require_adult("son1")


def test_require_adult_passes_for_adult(tmp_registry, monkeypatch):
    monkeypatch.setattr(permissions, "get_registry", lambda: tmp_registry)
    tmp_registry.add_member(telegram_id="121095851", alias="friend")
    permissions.require_adult("friend")


# ─── 영속화 ───────────────────────────────────────────
def test_registry_persistence(tmp_registry, monkeypatch):
    tmp_registry.add_member(telegram_id="121095851", alias="wife", is_minor=False)
    tmp_registry.add_member(telegram_id="345678901", alias="son1", is_minor=True)
    # 같은 파일로 새 인스턴스 로드
    fresh = UserRegistry(tmp_registry._path)
    assert fresh.get("wife").display_name == "wife"
    assert fresh.get("son1").is_minor is True
    assert fresh.is_admin("tg_109494677") is True
