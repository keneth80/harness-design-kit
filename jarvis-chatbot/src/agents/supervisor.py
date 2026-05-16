"""LangGraph supervisor: 라우팅(chat / rag) → worker → END."""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from src.core.llm import LMStudioClient
from src.core.logger import get_logger
from src.dashboard.events import get_bus
from src.memory.rag_store import RagStore
from src.agents.chat_agent import chat_agent_node
from src.agents.rag_agent import rag_agent_node

_log = get_logger("agents.supervisor")
_bus = get_bus()

Route = Literal["chat", "rag"]


class GraphState(TypedDict, total=False):
    messages: list[dict[str, str]]
    user_id: str
    is_admin: bool
    session_id: str
    user_message: str
    force_mode: str  # "chat" | "rag" | "" (auto)
    route: Route
    reply: str
    retrieved_docs: list
    error: str
    trace_id: str


_RAG_KEYWORDS = (
    "?",
    "알려줘",
    "알려",
    "설명",
    "찾아",
    "뭐야",
    "무엇",
    "어떻게",
    "왜",
    "어디",
    "언제",
    "누가",
    "검색",
    "문서",
)

_ROUTER_SYSTEM = (
    "당신은 라우터입니다. 사용자 메시지를 보고 'chat' 또는 'rag' 중 하나를 결정해 JSON 한 줄로만 답합니다. "
    "판정 기준: "
    "rag → 저장된 문서/지식에서 찾아야 정확히 답할 수 있는 사실 질문, 특정 자료 검색, '문서에 따르면' 류. "
    "chat → 인사, 잡담, 의견 요청, 창의적 글쓰기, 일반 상식·코딩 도움처럼 문서 없이도 답할 수 있는 것. "
    '출력 예시: {"route":"chat"} 또는 {"route":"rag"} (이외 텍스트 금지).'
)


def _heuristic_route(user_message: str, rag_count: int) -> Route:
    if rag_count == 0:
        return "chat"
    text = user_message.lower()
    if any(k in text for k in _RAG_KEYWORDS):
        return "rag"
    return "chat"


_JSON_OBJ_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _extract_route(raw: str) -> Route | None:
    """LLM 응답 텍스트에서 {"route":"..."} 찾기. 코드펜스/잡음에 강건."""
    if not raw:
        return None
    m = _JSON_OBJ_RE.search(raw)
    if not m:
        # 마지막 단어가 chat/rag일 수도 있음
        last = raw.strip().lower().split()[-1] if raw.strip() else ""
        if last in ("chat", "rag"):
            return last  # type: ignore[return-value]
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    r = str(obj.get("route", "")).lower().strip()
    return "rag" if r == "rag" else ("chat" if r == "chat" else None)


async def _llm_route(client, user_message: str, trace_id: str) -> Route:
    """LLM JSON 라우팅. 실패 시 휴리스틱으로 fallback."""
    msgs = [
        {"role": "system", "content": _ROUTER_SYSTEM},
        {"role": "user", "content": user_message[:500]},
    ]
    try:
        raw = await client.chat(msgs, temperature=0.0, trace_id=trace_id, max_tokens=32)
        route = _extract_route(raw)
        if route is None:
            _log.bind(trace_id=trace_id).warning(f"llm_route unparseable: {raw[:80]!r}")
            return _heuristic_route(user_message, rag_count=1)
        return route
    except Exception as e:
        _log.bind(trace_id=trace_id).warning(f"llm_route fallback: {e}")
        return _heuristic_route(user_message, rag_count=1)


def build_graph(client: LMStudioClient, store: RagStore):
    """체크포인터 포함 컴파일된 LangGraph 반환."""

    async def supervisor_node(state: GraphState) -> GraphState:
        trace_id = state.get("trace_id") or uuid.uuid4().hex[:8]
        force = state.get("force_mode", "")
        user_id = state.get("user_id", "")
        is_admin = bool(state.get("is_admin", False))
        rag_count = store.count_shared()
        if not is_admin and user_id:
            rag_count += store.count_for_user(user_id)
        decided_by: str
        if force in ("chat", "rag"):
            route: Route = force  # type: ignore[assignment]
            decided_by = "force"
        elif rag_count == 0:
            route = "chat"
            decided_by = "empty_rag"
        else:
            route = await _llm_route(client, state["user_message"], trace_id)
            decided_by = "llm"
        _bus.publish(
            "supervisor.route",
            {
                "route": route,
                "force": force or None,
                "rag_docs": rag_count,
                "decided_by": decided_by,
            },
            trace_id=trace_id,
        )
        _log.bind(trace_id=trace_id).info(
            f"route={route} by={decided_by} force={force or '-'}"
        )
        return {**state, "route": route, "trace_id": trace_id}

    async def chat_node(state: GraphState) -> GraphState:
        return await chat_agent_node(state, client=client)

    async def rag_node(state: GraphState) -> GraphState:
        return await rag_agent_node(state, client=client, store=store)

    def _route_decision(state: GraphState) -> str:
        return state.get("route", "chat")

    graph = StateGraph(GraphState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("chat", chat_node)
    graph.add_node("rag", rag_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route_decision,
        {"chat": "chat", "rag": "rag"},
    )
    graph.add_edge("chat", END)
    graph.add_edge("rag", END)

    return graph.compile(checkpointer=InMemorySaver())


async def _smoke() -> None:
    client = LMStudioClient()
    store = RagStore()
    app = build_graph(client, store)
    state: GraphState = {
        "messages": [
            {"role": "system", "content": "당신은 JARVIS입니다. 한국어로 간결히 답합니다."},
            {"role": "user", "content": "JARVIS는 어떤 DB를 쓰나?"},
        ],
        "user_id": "u1",
        "session_id": "s1",
        "user_message": "JARVIS는 어떤 DB를 쓰나?",
    }
    config = {"configurable": {"thread_id": "s1"}}
    result = await app.ainvoke(state, config=config)
    print(f"route: {result.get('route')}")
    print(f"reply: {result.get('reply')}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(_smoke())
