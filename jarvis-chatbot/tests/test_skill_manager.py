"""Skill manager 단위 + PII 마스킹 + minor 필터 테스트."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from src.self_improvement.skill_manager import SkillManager, _slugify
from src.self_improvement.user_registry import UserRegistry


class FakeClient:
    def __init__(self, response: dict | str) -> None:
        if isinstance(response, dict):
            response = json.dumps(response, ensure_ascii=False)
        self._response = response

    async def chat(self, messages, **kwargs):
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
    return tmp, reg


# ─── slugify ──────────────────────────────────────
def test_slugify():
    assert _slugify("Make Coffee") == "make_coffee"
    assert _slugify("RAG 검색!") == "rag"  # 한글 제거
    assert _slugify("a-b_c") == "a_b_c"


# ─── 추출 + PII 마스킹 ─────────────────────────────
@pytest.mark.asyncio
async def test_extract_masks_api_key(env):
    tmp, reg = env
    fake = FakeClient(
        {
            "name": "deploy_app",
            "description": "OpenAI 키로 배포",
            "steps": [
                "1. export OPENAI_API_KEY=sk-abcdef1234567890abcdefghij",
                "2. python deploy.py",
            ],
            "adult_only": False,
            "tags": ["deploy", "ai"],
        }
    )
    sm = SkillManager(tmp, client=fake, registry=reg)
    name = await sm.maybe_extract("tg_109494677", [{"role": "user", "content": "x"}])
    assert name == "deploy_app"
    body = (tmp / "skills" / "deploy_app.md").read_text(encoding="utf-8")
    assert "sk-abcdef" not in body
    assert "<API_KEY_REDACTED>" in body


@pytest.mark.asyncio
async def test_extract_masks_email_and_phone(env):
    tmp, reg = env
    fake = FakeClient(
        {
            "name": "contact_flow",
            "description": "alice@example.com 010-1234-5678 로 연락",
            "steps": ["메일 보내기 alice@example.com"],
            "adult_only": False,
            "tags": [],
        }
    )
    sm = SkillManager(tmp, client=fake, registry=reg)
    name = await sm.maybe_extract("tg_109494677", [{"role": "user", "content": "x"}])
    body = (tmp / "skills" / name + ".md").read_text(encoding="utf-8") if False else (
        tmp / "skills" / f"{name}.md"
    ).read_text(encoding="utf-8")
    assert "alice@example.com" not in body
    assert "010-1234-5678" not in body


@pytest.mark.asyncio
async def test_extract_empty_skill_skipped(env):
    tmp, reg = env
    fake = FakeClient({"name": ""})
    sm = SkillManager(tmp, client=fake, registry=reg)
    name = await sm.maybe_extract("tg_109494677", [{"role": "user", "content": "x"}])
    assert name is None


@pytest.mark.asyncio
async def test_extract_invalid_json_skipped(env):
    tmp, reg = env
    fake = FakeClient("이건 JSON 아님")
    sm = SkillManager(tmp, client=fake, registry=reg)
    name = await sm.maybe_extract("tg_109494677", [{"role": "user", "content": "x"}])
    assert name is None


# ─── minor 필터 ────────────────────────────────────
@pytest.mark.asyncio
async def test_minor_excluded_from_adult_only(env):
    tmp, reg = env
    fake_adult = FakeClient(
        {
            "name": "wine_pairing",
            "description": "와인 페어링",
            "steps": ["1. 안주 선택"],
            "adult_only": True,
            "tags": ["food", "alcohol"],
        }
    )
    sm = SkillManager(tmp, client=fake_adult, registry=reg)
    await sm.maybe_extract("tg_109494677", [{"role": "user", "content": "x"}])

    fake_general = FakeClient(
        {
            "name": "make_kimchi",
            "description": "김치 만들기",
            "steps": ["1. 배추 절이기"],
            "adult_only": False,
            "tags": ["food"],
        }
    )
    sm2 = SkillManager(tmp, client=fake_general, registry=reg)
    await sm2.maybe_extract("tg_109494677", [{"role": "user", "content": "x"}])

    # 미성년자는 adult_only 스킬 안 보임
    minor_list = sm2.list_skills(user_id="son1")
    names = [s["name"] for s in minor_list]
    assert "make_kimchi" in names
    assert "wine_pairing" not in names

    # 성인은 둘 다 보임
    adult_list = sm2.list_skills(user_id="wife")
    names_a = [s["name"] for s in adult_list]
    assert "wine_pairing" in names_a
    assert "make_kimchi" in names_a


# ─── 검색 ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_find_relevant_matches_query(env):
    tmp, reg = env
    fake = FakeClient(
        {
            "name": "make_coffee",
            "description": "커피 내리기",
            "steps": ["1. 원두 갈기", "2. 에스프레소 추출"],
            "adult_only": False,
            "tags": ["beverage", "coffee"],
        }
    )
    sm = SkillManager(tmp, client=fake, registry=reg)
    await sm.maybe_extract("wife", [{"role": "user", "content": "x"}])

    hits = sm.find_relevant("wife", "커피 내려줘")
    assert hits
    assert hits[0]["name"] == "make_coffee"


# ─── 작성자 비공개 메타 ────────────────────────────
@pytest.mark.asyncio
async def test_created_by_recorded_in_meta(env):
    tmp, reg = env
    fake = FakeClient(
        {
            "name": "do_thing",
            "description": "x",
            "steps": ["1. x"],
            "adult_only": False,
            "tags": [],
        }
    )
    sm = SkillManager(tmp, client=fake, registry=reg)
    name = await sm.maybe_extract("wife", [{"role": "user", "content": "x"}])
    skill = sm.get(name)
    assert skill["created_by"] == "wife"
    # find_relevant 결과에는 created_by 노출 안 됨 (사용자 비공개)
    hits = sm.find_relevant("wife", "do thing")
    assert "created_by" not in hits[0]


# ─── 감사 로그 ────────────────────────────────────
@pytest.mark.asyncio
async def test_audit_records_creation(env):
    tmp, reg = env
    fake = FakeClient(
        {
            "name": "skill_x",
            "description": "x",
            "steps": [],
            "adult_only": False,
            "tags": [],
        }
    )
    sm = SkillManager(tmp, client=fake, registry=reg)
    await sm.maybe_extract("tg_109494677", [{"role": "user", "content": "x"}])
    audit = sm.audit_tail()
    assert any(e["action"] == "CREATE" and e["user_id"] == "tg_109494677" for e in audit)


# ─── client 없으면 추출 비활성 ─────────────────────
@pytest.mark.asyncio
async def test_no_client_extract_returns_none(env):
    tmp, reg = env
    sm = SkillManager(tmp, client=None, registry=reg)
    name = await sm.maybe_extract("wife", [{"role": "user", "content": "x"}])
    assert name is None
