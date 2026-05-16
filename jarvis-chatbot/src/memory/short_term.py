"""세션 내 단기 컨텍스트 빌더. long_term에서 최근 N턴을 가져와 messages로 조립."""
from __future__ import annotations

from typing import Any

from src.core.config import get_settings
from src.memory.long_term import LongTermMemory


SYSTEM_PROMPT_DEFAULT = (
    "당신은 사용자의 개인 비서 'JARVIS'입니다. "
    "한국어로 간결하고 정확하게 답합니다. "
    "사용자의 질문이 모호하면 가정을 명시하고 되묻습니다. "
    "이전 대화의 맥락을 활용하되 최신 발화를 우선합니다."
)


class ContextBuilder:
    def __init__(
        self,
        memory: LongTermMemory,
        *,
        system_prompt: str = SYSTEM_PROMPT_DEFAULT,
        window_turns: int | None = None,
    ) -> None:
        self._memory = memory
        self._system_prompt = system_prompt
        settings = get_settings()
        self._window_turns = window_turns or settings.context_window_turns

    async def build(
        self,
        *,
        session_id: str,
        user_message: str,
        prior_summary: str | None = None,
        extra_context: str | None = None,
        system_prompt_override: str | None = None,
    ) -> list[dict[str, str]]:
        """system → (prior summary) → (extra_context) → 최근 N턴 → user_message.

        system_prompt_override: ContextLoader가 빌드한 사용자별 system prompt.
        주어지면 self._system_prompt 대신 사용.
        """
        # 1턴 = user+assistant 2 메시지 → 메시지 단위 limit
        msg_limit = self._window_turns * 2
        recent = await self._memory.get_session_messages(session_id, limit=msg_limit)

        sys_prompt = system_prompt_override or self._system_prompt
        messages: list[dict[str, str]] = [
            {"role": "system", "content": sys_prompt}
        ]
        if prior_summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"[직전 세션 요약]\n{prior_summary}",
                }
            )
        if extra_context:
            messages.append(
                {
                    "role": "system",
                    "content": f"[참고 문서]\n{extra_context}",
                }
            )
        for m in recent:
            if m.role in ("user", "assistant"):
                messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": user_message})
        return messages


async def _smoke() -> None:
    mem = LongTermMemory()
    await mem.init()
    sid = await mem.start_session("ctx-test")
    await mem.add_message(session_id=sid, user_id="ctx-test", role="user", content="첫 질문")
    await mem.add_message(
        session_id=sid, user_id="ctx-test", role="assistant", content="첫 답변"
    )
    builder = ContextBuilder(mem)
    msgs = await builder.build(session_id=sid, user_message="후속 질문")
    for m in msgs:
        print(f"[{m['role']}] {m['content'][:60]}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(_smoke())
