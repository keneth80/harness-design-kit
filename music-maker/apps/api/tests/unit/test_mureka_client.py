"""MurekaClient unit tests using respx-mocked HTTPX."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.config import Settings
from app.core.exceptions import (
    MurekaPermanentError,
    MurekaTransientError,
)
from app.services.mureka_client import MurekaClient


def _settings() -> Settings:
    return Settings(
        mureka_api_base="https://api.mureka.test/v1",
        mureka_api_key="mk_test",  # type: ignore[arg-type]
        mureka_timeout_s=5,
    )


@pytest.mark.asyncio
@respx.mock
async def test_generate_song_returns_task_id():
    respx.post("https://api.mureka.test/v1/song/generate").mock(
        return_value=httpx.Response(
            200,
            json={"task_id": "task_abc", "state": "preparing"},
            headers={"x-trace-id": "mtrace-1"},
        )
    )
    async with MurekaClient(_settings(), max_retries=0) as client:
        task = await client.generate_song(
            lyrics=None, prompt="prompt text", model="auto", length_s=60
        )
    assert task.task_id == "task_abc"
    assert task.state == "pending"
    assert task.trace_id == "mtrace-1"


@pytest.mark.asyncio
@respx.mock
async def test_query_task_normalises_states_and_parses_items():
    respx.get("https://api.mureka.test/v1/task/task_abc").mock(
        return_value=httpx.Response(
            200,
            json={
                "task_id": "task_abc",
                "state": "succeeded",
                "stage": "rendering",
                "progress": 100,
                "items": [
                    {
                        "id": "song_1",
                        "url": "https://cdn.mureka.test/a.mp3",
                        "duration_ms": 60000,
                        "bpm": 90,
                        "key": "Cm",
                    },
                    {
                        "id": "song_2",
                        "url": "https://cdn.mureka.test/b.mp3",
                    },
                ],
            },
        )
    )
    async with MurekaClient(_settings(), max_retries=0) as client:
        status = await client.query_task("task_abc")
    assert status.state == "completed"  # mapped from `succeeded`
    assert len(status.items) == 2
    assert status.items[0].url.endswith("a.mp3")
    assert status.items[0].bpm == 90


@pytest.mark.asyncio
@respx.mock
async def test_4xx_is_permanent_no_retry():
    route = respx.post("https://api.mureka.test/v1/song/generate").mock(
        return_value=httpx.Response(400, json={"code": "bad_input", "message": "nope"})
    )
    async with MurekaClient(_settings(), max_retries=2, retry_base_delay_s=0.01) as client:
        with pytest.raises(MurekaPermanentError) as exc_info:
            await client.generate_song(lyrics=None, prompt="p")
    assert exc_info.value.code == "bad_input"
    assert route.call_count == 1  # no retry on 4xx


@pytest.mark.asyncio
@respx.mock
async def test_5xx_retries_then_succeeds():
    responses = [
        httpx.Response(500, json={"message": "fail1"}),
        httpx.Response(502, json={"message": "fail2"}),
        httpx.Response(
            200,
            json={"task_id": "task_after_retry", "state": "preparing"},
        ),
    ]
    route = respx.post("https://api.mureka.test/v1/song/generate").mock(side_effect=responses)
    async with MurekaClient(_settings(), max_retries=2, retry_base_delay_s=0.01) as client:
        task = await client.generate_song(lyrics=None, prompt="p")
    assert task.task_id == "task_after_retry"
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_5xx_exhausts_retries_raises_transient():
    respx.post("https://api.mureka.test/v1/song/generate").mock(
        return_value=httpx.Response(503, json={"message": "down"})
    )
    async with MurekaClient(_settings(), max_retries=1, retry_base_delay_s=0.01) as client:
        with pytest.raises(MurekaTransientError):
            await client.generate_song(lyrics=None, prompt="p")


@pytest.mark.asyncio
@respx.mock
async def test_generate_lyrics_extracts_text():
    respx.post("https://api.mureka.test/v1/lyrics/generate").mock(
        return_value=httpx.Response(200, json={"lyrics": "도시는 잠들지 않아", "language": "ko"})
    )
    async with MurekaClient(_settings(), max_retries=0) as client:
        out = await client.generate_lyrics("새벽 도쿄", "ko")
    assert "도시" in out.lyrics
    assert out.language == "ko"


# --- Real Mureka response-shape regression tests (observed 2026-05) ----------


@pytest.mark.asyncio
@respx.mock
async def test_error_payload_with_nested_error_object():
    """Mureka real shape: {"error": {"message": "..."}, "trace_id": "..."}."""
    respx.post("https://api.mureka.test/v1/lyrics/generate").mock(
        return_value=httpx.Response(
            429,
            json={
                "error": {"message": "You exceeded your current quota"},
                "trace_id": "5fedd311e9ad4b42a28dc4c5c236866e",
            },
        )
    )
    async with MurekaClient(_settings(), max_retries=0, retry_base_delay_s=0.01) as client:
        with pytest.raises(MurekaTransientError) as exc_info:
            await client.generate_lyrics("p", "ko")
    assert "exceeded your current quota" in str(exc_info.value)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
@respx.mock
async def test_trace_id_picked_up_from_body_when_header_missing():
    respx.post("https://api.mureka.test/v1/song/generate").mock(
        return_value=httpx.Response(
            200,
            json={
                "task_id": "task_bodytrace",
                "state": "preparing",
                "trace_id": "body-trace-123",
            },
            # No x-trace-id header on purpose
        )
    )
    async with MurekaClient(_settings(), max_retries=0) as client:
        task = await client.generate_song(lyrics=None, prompt="p")
    assert task.trace_id == "body-trace-123"


@pytest.mark.asyncio
@respx.mock
async def test_query_task_extracts_nested_error_object():
    respx.get("https://api.mureka.test/v1/task/task_failed").mock(
        return_value=httpx.Response(
            200,
            json={
                "task_id": "task_failed",
                "state": "failed",
                "error": {"code": "moderation_blocked", "message": "blocked"},
                "trace_id": "body-trace-err",
            },
        )
    )
    async with MurekaClient(_settings(), max_retries=0) as client:
        status = await client.query_task("task_failed")
    assert status.state == "failed"
    assert status.error_code == "moderation_blocked"
    assert status.error_message == "blocked"
    assert status.trace_id == "body-trace-err"


@pytest.mark.asyncio
@respx.mock
async def test_lyrics_extracted_from_nested_data_field():
    respx.post("https://api.mureka.test/v1/lyrics/generate").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"lyrics": "[Verse 1]\n안녕"}, "language": "ko"},
        )
    )
    async with MurekaClient(_settings(), max_retries=0) as client:
        out = await client.generate_lyrics("p", "ko")
    assert "안녕" in out.lyrics
