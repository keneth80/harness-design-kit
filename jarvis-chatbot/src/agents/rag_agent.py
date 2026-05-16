"""RAG 에이전트. RagStore 검색 → context 주입 → LLM 호출."""
from __future__ import annotations

import time
from typing import Any

from src.core.llm import LMStudioClient
from src.core.logger import get_logger
from src.dashboard.events import get_bus
from src.memory.rag_store import RagStore

_log = get_logger("agents.rag")
_bus = get_bus()


def _format_context(hits: list) -> str:
    if not hits:
        return ""
    parts = []
    for i, h in enumerate(hits, 1):
        src = h.metadata.get("source", "?")
        parts.append(f"[{i}] (source={src}, score={h.score:.2f})\n{h.text}")
    return "\n\n".join(parts)


async def rag_agent_node(
    state: dict[str, Any],
    *,
    client: LMStudioClient,
    store: RagStore,
) -> dict[str, Any]:
    trace_id = state.get("trace_id", "-")
    user_message = state["user_message"]
    base_messages = state["messages"]
    _bus.publish("agent.enter", {"node": "rag_agent"}, trace_id=trace_id)

    user_id = state.get("user_id", "")
    is_admin = bool(state.get("is_admin", False))
    hits = store.query_for(user_message, user_id=user_id, is_admin=is_admin)
    _bus.publish(
        "rag.query",
        {
            "user_id": user_id,
            "is_admin": is_admin,
            "question": user_message[:120],
            "hits": [
                {
                    "score": h.score,
                    "source": h.metadata.get("source", "?"),
                    "owner_id": h.metadata.get("owner_id", "-"),
                    "is_shared": h.metadata.get("is_shared", False),
                    "snippet": h.short(),
                }
                for h in hits
            ],
        },
        trace_id=trace_id,
    )
    context = _format_context(hits)

    messages = list(base_messages)
    if context:
        # system 메시지 뒤에 RAG context 주입
        insert_idx = 1 if messages and messages[0]["role"] == "system" else 0
        messages.insert(
            insert_idx,
            {"role": "system", "content": f"[관련 문서]\n{context}"},
        )

    started = time.time()
    try:
        reply = await client.chat(messages, temperature=0.4, trace_id=trace_id)
    except Exception as e:
        _log.bind(trace_id=trace_id).error(f"rag_agent error: {e}")
        _bus.publish(
            "agent.error", {"node": "rag_agent", "error": str(e)}, trace_id=trace_id
        )
        return {
            **state,
            "reply": "죄송합니다. 응답 생성 중 오류가 발생했습니다.",
            "retrieved_docs": [],
            "error": str(e),
        }
    elapsed = time.time() - started
    _bus.publish(
        "llm.call",
        {"node": "rag_agent", "elapsed_ms": int(elapsed * 1000), "len": len(reply)},
        trace_id=trace_id,
    )
    _bus.publish("agent.exit", {"node": "rag_agent"}, trace_id=trace_id)
    return {
        **state,
        "reply": reply,
        "retrieved_docs": [h.to_dict() if hasattr(h, "to_dict") else {"text": h.text, "score": h.score} for h in hits],
    }
