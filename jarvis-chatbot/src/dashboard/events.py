"""asyncio.Queue 기반 이벤트 버스. 모든 에이전트가 publish, 대시보드 SSE가 subscribe."""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

_MAX_BUFFER = 200


@dataclass
class Event:
    type: str
    payload: dict[str, Any]
    ts: float = field(default_factory=time.time)
    trace_id: str = "-"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "payload": self.payload,
            "ts": self.ts,
            "trace_id": self.trace_id,
        }

    def to_sse(self) -> str:
        return f"event: {self.type}\ndata: {json.dumps(self.to_dict(), ensure_ascii=False)}\n\n"


class EventBus:
    _instance: "EventBus | None" = None

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._buffer: deque[Event] = deque(maxlen=_MAX_BUFFER)
        self._stats: dict[str, int] = {}

    @classmethod
    def instance(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def publish(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        trace_id: str = "-",
    ) -> None:
        ev = Event(type=event_type, payload=payload or {}, trace_id=trace_id)
        self._buffer.append(ev)
        self._stats[event_type] = self._stats.get(event_type, 0) + 1
        for q in list(self._subscribers):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                pass

    async def subscribe(self) -> AsyncIterator[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        try:
            for ev in list(self._buffer):
                yield ev
            while True:
                ev = await q.get()
                yield ev
        finally:
            self._subscribers.remove(q)

    def recent(self, limit: int = 50) -> list[Event]:
        items = list(self._buffer)
        return items[-limit:]

    def stats(self) -> dict[str, int]:
        return dict(self._stats)


def get_bus() -> EventBus:
    return EventBus.instance()
