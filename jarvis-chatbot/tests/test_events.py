"""EventBus 단위 테스트."""
from __future__ import annotations

import asyncio

import pytest

from src.dashboard.events import EventBus


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


def test_publish_increments_stats(bus: EventBus) -> None:
    bus.publish("foo", {"x": 1})
    bus.publish("foo", {"x": 2})
    bus.publish("bar", {})
    assert bus.stats() == {"foo": 2, "bar": 1}


def test_recent_returns_buffer(bus: EventBus) -> None:
    for i in range(5):
        bus.publish("e", {"i": i})
    assert len(bus.recent()) == 5
    assert bus.recent(limit=2)[-1].payload == {"i": 4}


def test_sse_format(bus: EventBus) -> None:
    bus.publish("hello", {"k": "v"}, trace_id="abc")
    ev = bus.recent()[-1]
    sse = ev.to_sse()
    assert "event: hello\n" in sse
    assert '"trace_id": "abc"' in sse


@pytest.mark.asyncio
async def test_subscribe_replays_buffer() -> None:
    bus = EventBus()
    bus.publish("a", {"i": 1})
    bus.publish("b", {"i": 2})

    received = []

    async def consume() -> None:
        async for ev in bus.subscribe():
            received.append(ev.type)
            if len(received) >= 3:
                return

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    bus.publish("c", {"i": 3})
    await asyncio.wait_for(task, timeout=2.0)
    assert received == ["a", "b", "c"]
