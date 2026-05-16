"""Reflection 엔진.

- 사용자별 asyncio.Lock — 한 사용자의 자성이 다른 사용자를 막지 않는다.
- 전역 asyncio.Semaphore(2) — LM Studio 큐 폭주 방지.
- N턴마다(default 10) 자동 실행, 또는 force=True.
- 결과: MEMORY.md(new_memories) + USER.md(user_observations) 업데이트.
- skill_worthy 플래그만 기록 — 실제 skill 추출은 Phase 5.

보안:
  - 자성 프롬프트에 사용자 display_name 명시 → 다른 사용자 정보 무시 지시
  - 미성년자: 민감 관찰은 memory_store.update_user_profile에서 자동 차단
  - LLM 응답에 다른 사용자 별칭이 포함되면 (자기 메모리 안에) 거부
"""
from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from src.core.llm import LMStudioClient
from src.core.logger import get_logger
from src.dashboard.events import get_bus
from src.self_improvement.memory_store import MemoryStore
from src.self_improvement.user_registry import (
    UserRegistry,
    get_registry,
)

_log = get_logger("self_improvement.reflection")
_bus = get_bus()


_REFLECT_EVERY_N_TURNS = 10
_GLOBAL_CONCURRENCY = 2
_MAX_CONV_CHARS = 6000  # 최근 대화 truncation
_LLM_TEMPERATURE = 0.2
_LLM_MAX_TOKENS = 800


def _build_prompt(user, conversation_text: str, other_aliases: list[str]) -> list[dict]:
    """다른 사용자 별칭 목록을 명시해 혼동 방지."""
    minor_note = (
        "이 사용자는 미성년자입니다. 감정·갈등·가족 문제·재정·성·약물 등 "
        "발달에 부적절한 사실은 절대 출력하지 마세요."
        if user.is_minor
        else ""
    )
    other_block = (
        f"다른 가족 구성원 별칭: {', '.join(other_aliases)} — "
        f"대화에서 이들의 정보가 보이더라도 출력에 포함하지 마세요."
        if other_aliases
        else ""
    )
    sys = (
        f"당신은 {user.display_name}님 한 사람의 대화 기록을 정리하는 분석가입니다. "
        "최근 대화에서 (1) 장기 기억할 만한 사실, (2) 사용자 프로필 관찰, "
        "(3) 향후 재사용 가능한 절차/skill 후보 여부를 JSON 한 덩어리로 출력합니다.\n\n"
        f"{minor_note}\n{other_block}\n\n"
        "출력 JSON 스키마:\n"
        '{\n'
        '  "new_memories": [{"section": "사실|진행 중인 과제|보류/추후", "fact": "..."}],\n'
        '  "user_observations": [{"section": "선호|관심사|컨텍스트", "obs": "..."}],\n'
        '  "skill_worthy": false,\n'
        '  "skill_hint": "..."  // skill_worthy=true일 때만 의미 있음, 절차 요약\n'
        "}\n"
        "출력은 JSON 객체 하나만. 추가 설명 금지. 비어도 빈 배열 사용."
    )
    return [
        {"role": "system", "content": sys},
        {"role": "user", "content": f"=== 최근 대화 ===\n{conversation_text}"},
    ]


_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")


def _parse_reflection(raw: str) -> dict[str, Any]:
    """LLM 응답에서 JSON 블록 추출. 실패 시 빈 dict."""
    if not raw:
        return {}
    m = _JSON_BLOCK.search(raw)
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}


def _format_conversation(messages: list[dict]) -> str:
    """OpenAI messages → 텍스트. 시스템 메시지는 제외."""
    lines = []
    for m in messages:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = (m.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"[{role}] {content}")
    text = "\n".join(lines)
    if len(text) > _MAX_CONV_CHARS:
        text = text[-_MAX_CONV_CHARS:]
    return text


@dataclass
class ReflectionResult:
    user_id: str
    new_memories: list[dict] = field(default_factory=list)
    user_observations: list[dict] = field(default_factory=list)
    skill_worthy: bool = False
    skill_hint: str = ""
    raw: str = ""
    error: str | None = None


class ReflectionEngine:
    def __init__(
        self,
        memory_store: MemoryStore,
        client: LMStudioClient,
        *,
        registry: UserRegistry | None = None,
        reflect_every: int = _REFLECT_EVERY_N_TURNS,
        global_concurrency: int = _GLOBAL_CONCURRENCY,
        skill_manager=None,
    ) -> None:
        self._memory = memory_store
        self._client = client
        self._registry = registry or get_registry()
        self._every = reflect_every
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._counters: dict[str, int] = defaultdict(int)
        self._sem = asyncio.Semaphore(global_concurrency)
        self._skill_manager = skill_manager

    def turn_count(self, user_id: str) -> int:
        return self._counters[user_id]

    def increment(self, user_id: str) -> None:
        self._counters[user_id] += 1

    async def maybe_reflect(
        self,
        user_id: str,
        conversation: list[dict],
        *,
        force: bool = False,
    ) -> ReflectionResult | None:
        # 검증 (UnauthorizedError raises)
        user = self._registry.get(user_id)

        # 카운터 기반 게이트
        if not force:
            if self._counters[user_id] < self._every:
                return None

        async with self._locks[user_id]:
            # double-check 후 리셋
            if not force and self._counters[user_id] < self._every:
                return None
            self._counters[user_id] = 0

            other_aliases = [
                u.user_id for u in self._registry.list_users() if u.user_id != user_id
            ]
            conv_text = _format_conversation(conversation)
            if not conv_text:
                return None
            prompt = _build_prompt(user, conv_text, other_aliases)

            _bus.publish(
                "reflection.start",
                {"user_id": user_id, "is_minor": user.is_minor},
            )
            async with self._sem:
                try:
                    raw = await self._client.chat(
                        prompt,
                        temperature=_LLM_TEMPERATURE,
                        max_tokens=_LLM_MAX_TOKENS,
                    )
                except Exception as e:
                    _log.bind(trace_id="-").error(
                        f"reflection LLM error uid={user_id}: {e}"
                    )
                    _bus.publish(
                        "reflection.error",
                        {"user_id": user_id, "error": str(e)},
                    )
                    return ReflectionResult(user_id=user_id, error=str(e))

            obj = _parse_reflection(raw)
            if not obj:
                _log.warning(f"reflection parse failed uid={user_id}: {raw[:120]!r}")
                _bus.publish(
                    "reflection.parse_failed",
                    {"user_id": user_id, "raw_preview": raw[:120]},
                )
                return ReflectionResult(user_id=user_id, raw=raw, error="parse")

            result = ReflectionResult(
                user_id=user_id,
                new_memories=list(obj.get("new_memories") or []),
                user_observations=list(obj.get("user_observations") or []),
                skill_worthy=bool(obj.get("skill_worthy", False)),
                skill_hint=str(obj.get("skill_hint", "") or ""),
                raw=raw,
            )

            # 다른 사용자 별칭이 출력에 등장하면 그 항목만 누락
            applied_mem = 0
            for m in result.new_memories:
                fact = str(m.get("fact", "")).strip()
                section = str(m.get("section", "사실")).strip() or "사실"
                if not fact:
                    continue
                if self._mentions_other_user(fact, other_aliases):
                    _log.warning(
                        f"reflection mentions other user — skip fact uid={user_id}: {fact[:60]!r}"
                    )
                    continue
                try:
                    self._memory.append_memory(user_id, section, fact)
                    applied_mem += 1
                except Exception as e:
                    _log.warning(f"memory append failed uid={user_id}: {e}")

            applied_obs = 0
            for o in result.user_observations:
                obs = str(o.get("obs", "")).strip()
                section = str(o.get("section", "컨텍스트")).strip() or "컨텍스트"
                if not obs:
                    continue
                if self._mentions_other_user(obs, other_aliases):
                    _log.warning(
                        f"reflection mentions other user — skip obs uid={user_id}"
                    )
                    continue
                try:
                    ok = self._memory.update_user_profile(user_id, section, obs)
                    if ok:
                        applied_obs += 1
                except Exception as e:
                    _log.warning(f"profile update failed uid={user_id}: {e}")

            # skill 추출 (옵션)
            skill_name = None
            if result.skill_worthy and self._skill_manager is not None:
                try:
                    skill_name = await self._skill_manager.maybe_extract(
                        user_id, conversation, hint=result.skill_hint
                    )
                    if skill_name:
                        _bus.publish(
                            "skill.created",
                            {"user_id": user_id, "name": skill_name},
                        )
                except Exception as e:
                    _log.warning(f"skill extract failed uid={user_id}: {e}")

            _bus.publish(
                "reflection.done",
                {
                    "user_id": user_id,
                    "memories": applied_mem,
                    "observations": applied_obs,
                    "skill_worthy": result.skill_worthy,
                    "skill_name": skill_name,
                },
            )
            _log.info(
                f"reflection uid={user_id} mem+={applied_mem} obs+={applied_obs} "
                f"skill_worthy={result.skill_worthy} skill={skill_name}"
            )
            return result

    @staticmethod
    def _mentions_other_user(text: str, other_aliases: list[str]) -> bool:
        if not other_aliases:
            return False
        return any(alias in text for alias in other_aliases)
