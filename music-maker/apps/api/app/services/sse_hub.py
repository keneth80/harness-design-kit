"""SSE Hub — Redis Pub/Sub bridge.

Workers publish to channel `gen:{generation_id}`. The SSE endpoint subscribes
and streams JSON-encoded events to the browser.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis_async
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


def channel_for(generation_id: str) -> str:
    return f"gen:{generation_id}"


_async_redis: redis_async.Redis | None = None


def get_async_redis() -> redis_async.Redis:
    """Return a module-level async Redis client (lazy)."""
    global _async_redis
    if _async_redis is None:
        settings = get_settings()
        _async_redis = redis_async.from_url(
            settings.redis_url, decode_responses=True
        )
    return _async_redis


async def publish_async(generation_id: str, payload: dict[str, Any]) -> int:
    """Async publish — used by HTTP layer (rare). Returns subscriber count."""
    r = get_async_redis()
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return await r.publish(channel_for(generation_id), data)


def publish_sync(generation_id: str, payload: dict[str, Any]) -> int:
    """Sync publish — used by Celery worker. Returns subscriber count."""
    import redis as redis_sync

    settings = get_settings()
    client = redis_sync.from_url(settings.redis_url, decode_responses=True)
    try:
        data = json.dumps(payload, ensure_ascii=False, default=str)
        return client.publish(channel_for(generation_id), data)
    finally:
        client.close()


async def subscribe(generation_id: str):
    """Async generator yielding decoded JSON events for an SSE response.

    Caller must wrap each yielded dict as ``data: {json}\\n\\n``.
    """
    r = get_async_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel_for(generation_id))
    try:
        async for message in pubsub.listen():
            if message is None:
                continue
            if message.get("type") != "message":
                continue
            try:
                yield json.loads(message["data"])
            except (TypeError, ValueError):
                log.warning("sse.bad_message", data=message.get("data"))
                continue
    finally:
        await pubsub.unsubscribe(channel_for(generation_id))
        await pubsub.close()
