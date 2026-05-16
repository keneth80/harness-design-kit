"""텔레그램 4096자 분할 로직 단위 테스트."""
from __future__ import annotations


def _split(text: str, limit: int = 4096) -> list[str]:
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def test_short_text_single_chunk() -> None:
    assert _split("hello") == ["hello"]


def test_exact_limit_is_single() -> None:
    s = "a" * 4096
    parts = _split(s)
    assert len(parts) == 1
    assert parts[0] == s


def test_overflow_splits() -> None:
    s = "a" * 4097
    parts = _split(s)
    assert len(parts) == 2
    assert len(parts[0]) == 4096
    assert parts[1] == "a"


def test_double_overflow() -> None:
    s = "x" * (4096 * 2 + 10)
    parts = _split(s)
    assert [len(p) for p in parts] == [4096, 4096, 10]
    assert "".join(parts) == s


def test_empty_returns_empty() -> None:
    assert _split("") == []
