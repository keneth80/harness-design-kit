"""라우터 휴리스틱과 JSON 파서 단위 테스트 (외부 호출 없음)."""
from __future__ import annotations

from src.agents.supervisor import _extract_route, _heuristic_route


def test_heuristic_empty_rag_always_chat() -> None:
    assert _heuristic_route("아무 질문?", rag_count=0) == "chat"


def test_heuristic_question_routes_rag() -> None:
    assert _heuristic_route("이 문서가 뭐야?", rag_count=10) == "rag"


def test_heuristic_greeting_routes_chat() -> None:
    assert _heuristic_route("안녕!", rag_count=10) == "chat"


def test_extract_route_clean_json() -> None:
    assert _extract_route('{"route":"rag"}') == "rag"
    assert _extract_route('{"route":"chat"}') == "chat"


def test_extract_route_with_codefence() -> None:
    raw = '```json\n{"route": "rag"}\n```'
    assert _extract_route(raw) == "rag"


def test_extract_route_with_prefix_text() -> None:
    raw = '판단 결과: {"route":"chat"}'
    assert _extract_route(raw) == "chat"


def test_extract_route_invalid_returns_none() -> None:
    assert _extract_route("이상한 응답") is None
    assert _extract_route("") is None


def test_extract_route_bare_word_fallback() -> None:
    assert _extract_route("rag") == "rag"
    assert _extract_route("최종 결정: chat") == "chat"
