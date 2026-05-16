"""사용자별 컨텍스트 조립.

build_system_prompt(user_id, ...)는 다음을 순서대로 system prompt에 주입한다:
  1. base_prompt (호출자가 제공)
  2. 대화 상대 인사 (display_name + 언어)
  3. USER.md (사용자 프로필)
  4. MEMORY.md (사용자 메모)
  5. (공유 메모리 — Phase 2)
  6. (관련 과거 세션 — Phase 3)
  7. (관련 skill — Phase 5)

각 섹션은 최대 문자수 한도로 잘림.
"""
from __future__ import annotations

from src.core.logger import get_logger
from src.self_improvement.memory_store import MemoryStore
from src.self_improvement.user_registry import UserRegistry, get_registry

_log = get_logger("self_improvement.context")


# 한국어 기준 대략적 캐릭터 한도 (≈ 토큰 × 1.5)
_LIMITS = {
    "user_profile": 2500,
    "user_memory": 4000,
    "shared_memory": 1500,
    "session_history": 2500,
    "skills": 3000,
}


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit("\n", 1)[0] + "\n…(이하 생략)"


class ContextLoader:
    def __init__(
        self,
        memory_store: MemoryStore,
        registry: UserRegistry | None = None,
    ) -> None:
        self._memory = memory_store
        self._registry = registry or get_registry()
        # 후속 phase에서 주입
        self._shared_memory = None
        self._session_search = None
        self._skill_manager = None

    def attach_shared_memory(self, shared_memory) -> None:
        self._shared_memory = shared_memory

    def attach_session_search(self, session_search) -> None:
        self._session_search = session_search

    def attach_skill_manager(self, skill_manager) -> None:
        self._skill_manager = skill_manager

    def build_system_prompt(
        self,
        *,
        user_id: str,
        base_prompt: str,
        user_message: str,
        agent_id: str | None = None,
    ) -> str:
        user = self._registry.get(user_id)  # 검증 + raise on unknown

        parts: list[str] = [base_prompt.strip()]

        parts.append(
            f"# 대화 상대\n{user.display_name}님과 {user.language}로 대화 중입니다."
        )
        if agent_id:
            parts.append(f"(에이전트: {agent_id})")

        profile = self._memory.get_user_profile(user_id).strip()
        if profile:
            parts.append(
                "# 사용자 프로필 (USER.md)\n"
                + _truncate(profile, _LIMITS["user_profile"])
            )

        memory = self._memory.get_memory(user_id).strip()
        if memory:
            parts.append(
                "# 사용자 메모리 (MEMORY.md)\n"
                + _truncate(memory, _LIMITS["user_memory"])
            )

        # 공유 메모리 — 미성년자는 제외 (Phase 2에서 실제 구현)
        if self._shared_memory and not user.is_minor:
            try:
                shared = self._shared_memory.read(user_id).strip()
                if shared:
                    parts.append(
                        "# 가족 공유 메모리 (SHARED_MEMORY.md)\n"
                        + _truncate(shared, _LIMITS["shared_memory"])
                    )
            except Exception as e:
                _log.warning(f"shared memory read failed: {e}")

        # 관련 과거 세션 — Phase 3
        if self._session_search:
            try:
                hits = self._session_search.search(
                    user_id, user_message, top_k=3
                )
                if hits:
                    formatted = self._format_sessions(hits)
                    parts.append(
                        "# 관련 과거 대화\n"
                        + _truncate(formatted, _LIMITS["session_history"])
                    )
            except Exception as e:
                _log.warning(f"session search failed: {e}")

        # 관련 skill — Phase 5
        if self._skill_manager:
            try:
                skills = self._skill_manager.find_relevant(user_id, user_message)
                if skills:
                    formatted = self._format_skills(skills)
                    parts.append(
                        "# 활용 가능한 절차\n" + _truncate(formatted, _LIMITS["skills"])
                    )
            except Exception as e:
                _log.warning(f"skill find failed: {e}")

        return "\n\n".join(parts)

    def _format_sessions(self, hits: list) -> str:
        out = []
        for h in hits:
            ts = h.get("ts", "?")
            role = h.get("role", "?")
            content = (h.get("content") or "").strip().replace("\n", " ")[:200]
            out.append(f"- [{ts}] [{role}] {content}")
        return "\n".join(out)

    def _format_skills(self, skills: list) -> str:
        out = []
        for s in skills:
            name = s.get("name", "?")
            desc = (s.get("description") or "").strip().replace("\n", " ")[:120]
            out.append(f"- **{name}**: {desc}")
        return "\n".join(out)
