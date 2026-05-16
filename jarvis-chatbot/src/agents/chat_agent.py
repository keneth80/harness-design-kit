"""일반 대화 에이전트. LM Studio chat completion 호출."""
from __future__ import annotations

import time
from typing import Any

from src.core.llm import LMStudioClient
from src.core.logger import get_logger
from src.dashboard.events import get_bus

_log = get_logger("agents.chat")
_bus = get_bus()


async def chat_agent_node(
    state: dict[str, Any], *, client: LMStudioClient
) -> dict[str, Any]:
    trace_id = state.get("trace_id", "-")
    messages = state["messages"]
    _bus.publish("agent.enter", {"node": "chat_agent"}, trace_id=trace_id)
    started = time.time()
    try:
        reply = await client.chat(messages, temperature=0.7, trace_id=trace_id)
    except Exception as e:
        _log.bind(trace_id=trace_id).error(f"chat_agent error: {e}")
        _bus.publish(
            "agent.error", {"node": "chat_agent", "error": str(e)}, trace_id=trace_id
        )
        return {**state, "reply": "죄송합니다. 응답 생성 중 오류가 발생했습니다.", "error": str(e)}
    elapsed = time.time() - started
    _bus.publish(
        "llm.call",
        {"node": "chat_agent", "elapsed_ms": int(elapsed * 1000), "len": len(reply)},
        trace_id=trace_id,
    )
    _bus.publish("agent.exit", {"node": "chat_agent"}, trace_id=trace_id)
    return {**state, "reply": reply}
