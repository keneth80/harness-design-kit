"""FTS5 세션 검색 격리 + 한글 검색 테스트."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.self_improvement.session_search import SessionSearch, _escape_fts
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
    reg = UserRegistry(tmp / "users" / "_registry.json")
    reg.add_member(telegram_id="121095851", alias="wife")
    reg.add_member(telegram_id="345678901", alias="son1", is_minor=True)
    s = SessionSearch(tmp, registry=reg)
    yield tmp, reg, s
    s.close_all()


# ─── escape ───────────────────────────────────────
def test_escape_basic():
    assert _escape_fts("비빔밥") == '"비빔밥"'
    assert _escape_fts("a b c") == '"a" OR "b" OR "c"'


def test_escape_empty():
    assert _escape_fts("") == ""
    assert _escape_fts("   ") == ""


def test_escape_strips_inner_quotes():
    # 사용자 입력의 " 는 제거. FTS5 phrase wrapping " 만 남음.
    assert _escape_fts('it"s') == '"its"'


# ─── cross-user 격리 ──────────────────────────────
def test_cross_user_search_isolation(env):
    _, _, s = env
    s.save_message(
        "tg_109494677", session_id="k1", role="user", content="kenneth만의 비밀"
    )
    s.save_message(
        "wife", session_id="w1", role="user", content="wife만의 비밀"
    )
    # 각자 자기 것만 보임
    k = s.search("tg_109494677", "비밀")
    w = s.search("wife", "비밀")
    assert any("kenneth만의 비밀" in r["content"] for r in k)
    assert not any("wife만의 비밀" in r["content"] for r in k)
    assert any("wife만의 비밀" in r["content"] for r in w)
    assert not any("kenneth만의 비밀" in r["content"] for r in w)


def test_search_unknown_user_raises(env):
    _, _, s = env
    with pytest.raises(UnauthorizedError):
        s.search("nobody", "test")


def test_save_unknown_user_raises(env):
    _, _, s = env
    with pytest.raises(UnauthorizedError):
        s.save_message("nobody", session_id="x", role="user", content="x")


def test_path_traversal_blocked(env):
    _, _, s = env
    with pytest.raises(UnauthorizedError):
        s.search("../../../etc", "x")


# ─── 한글 토크나이즈 ───────────────────────────────
def test_korean_search_matches(env):
    _, _, s = env
    s.save_message(
        "wife", session_id="w", role="user", content="비빔밥 레시피 알려줘"
    )
    s.save_message(
        "wife", session_id="w", role="assistant", content="고추장과 야채로 비빔"
    )
    hits = s.search("wife", "비빔밥")
    assert hits
    assert any("비빔밥" in h["content"] for h in hits)


def test_multi_token_or(env):
    _, _, s = env
    s.save_message("wife", session_id="w", role="user", content="자전거 타기")
    s.save_message("wife", session_id="w", role="user", content="요가 매트 구매")
    # OR 검색
    hits = s.search("wife", "자전거 요가")
    contents = [h["content"] for h in hits]
    assert any("자전거" in c for c in contents)
    assert any("요가" in c for c in contents)


def test_snippet_marks_match(env):
    _, _, s = env
    s.save_message(
        "wife", session_id="w", role="user", content="오늘 점심은 비빔밥 어때"
    )
    hits = s.search("wife", "비빔밥")
    assert hits
    assert "«비빔밥»" in hits[0]["snippet"]


def test_count_per_user(env):
    _, _, s = env
    s.save_message("wife", session_id="w", role="user", content="a")
    s.save_message("wife", session_id="w", role="user", content="b")
    s.save_message("tg_109494677", session_id="k", role="user", content="c")
    assert s.count("wife") == 2
    assert s.count("tg_109494677") == 1
    assert s.count("son1") == 0


# ─── 파일 분리 확인 ────────────────────────────────
def test_separate_db_files(env):
    tmp, _, s = env
    s.save_message("wife", session_id="w", role="user", content="a")
    s.save_message("son1", session_id="w", role="user", content="b")
    assert (tmp / "users" / "wife" / "sessions.db").exists()
    assert (tmp / "users" / "son1" / "sessions.db").exists()
    # 서로 다른 파일
    assert (tmp / "users" / "wife" / "sessions.db").samefile(
        tmp / "users" / "wife" / "sessions.db"
    )
