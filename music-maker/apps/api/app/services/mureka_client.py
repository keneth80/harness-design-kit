"""Async Mureka REST client.

The exact response shape of Mureka's public API is not yet pinned down in the
public docs (see `docs/03-Architecture.md` appendix A). We therefore:

1. Make every method return a Pydantic model (`LyricsResult`, `TaskResponse`,
   `MurekaTaskStatus`) so the rest of the code is decoupled from the wire
   format.
2. Be permissive when *reading* fields and only *require* the minimum needed
   (`task_id`, `state`, `items` for completed). Add new fields as needed.
3. Map heterogeneous state names (`pending|preparing|queued|running|succeeded|completed|failed`)
   to our internal taxonomy (`pending|running|completed|failed`).

If Mureka's actual fields differ, change ONLY the `_parse_*` helpers below
and the Pydantic models — every caller is shielded.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

import httpx
import structlog
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.core.exceptions import (
    MurekaPermanentError,
    MurekaTransientError,
)
from app.core.tracing import get_trace_id

log = structlog.get_logger(__name__)

# Map Mureka raw states -> internal canonical states.
_STATE_MAP: dict[str, str] = {
    "pending": "pending",
    "preparing": "pending",
    "queued": "pending",
    "submitted": "pending",
    "running": "running",
    "processing": "running",
    "in_progress": "running",
    "completed": "completed",
    "succeeded": "completed",
    "success": "completed",
    "failed": "failed",
    "error": "failed",
    "cancelled": "failed",
}


class LyricsResult(BaseModel):
    """Result from `POST /lyrics/generate`."""

    lyrics: str
    language: str = "ko"
    raw: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    """Returned by `POST /song/generate` or `/instrumental/generate`.

    The actual job hasn't started yet — caller must poll via `query_task`.
    """

    task_id: str
    state: str = "pending"
    trace_id: str | None = None


class MurekaTaskItem(BaseModel):
    """One variant inside a completed task."""

    id: str | None = None
    url: str
    duration_ms: int | None = None
    bpm: int | None = None
    key: str | None = None
    cover_url: str | None = None
    genres: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)


class MurekaTaskStatus(BaseModel):
    """Normalised task status from `GET /task/{id}`."""

    task_id: str
    state: Literal["pending", "running", "completed", "failed"] = "pending"
    stage: str | None = None
    progress: int | None = None
    items: list[MurekaTaskItem] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    trace_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


def _normalise_state(value: Any) -> str:
    if not isinstance(value, str):
        return "pending"
    return _STATE_MAP.get(value.lower(), "pending")


def _extract_error(payload: dict[str, Any] | None, status_code: int) -> tuple[str, str]:
    """Return (code, message) from a Mureka error payload.

    Mureka observed (2026-05): `{"error": {"message": "..."}, "trace_id": "..."}`.
    Legacy/alternative shape also supported: `{"code": ..., "message": ...}`.
    """
    if not isinstance(payload, dict):
        return f"http_{status_code}", ""
    err = payload.get("error")
    if isinstance(err, dict):
        return (
            err.get("code") or payload.get("code") or f"http_{status_code}",
            err.get("message") or "",
        )
    if isinstance(err, str):
        return f"http_{status_code}", err
    return (
        payload.get("code") or f"http_{status_code}",
        payload.get("message") or "",
    )


def _extract_trace_id(
    response: httpx.Response, payload: dict[str, Any] | None = None
) -> str | None:
    """Mureka returns trace_id in the response body; older docs hinted at a header."""
    header_val = response.headers.get("x-trace-id")
    if header_val:
        return header_val
    if isinstance(payload, dict):
        body_val = payload.get("trace_id")
        if isinstance(body_val, str) and body_val:
            return body_val
    return None


def _parse_items(payload: dict[str, Any]) -> list[MurekaTaskItem]:
    """Tolerant parser — Mureka may put the result list under several keys."""
    raw_items = (
        payload.get("items")
        or payload.get("songs")
        or payload.get("results")
        or payload.get("variants")
        or []
    )
    if not isinstance(raw_items, list):
        return []
    items: list[MurekaTaskItem] = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        url = it.get("url") or it.get("audio_url") or it.get("mp3_url")
        if not url:
            continue
        items.append(
            MurekaTaskItem(
                id=it.get("id") or it.get("song_id"),
                url=url,
                duration_ms=it.get("duration_ms") or it.get("duration"),
                bpm=it.get("bpm"),
                key=it.get("key"),
                cover_url=it.get("cover_url") or it.get("image_url"),
                genres=it.get("genres") or [],
                moods=it.get("moods") or [],
            )
        )
    return items


def _retryable(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


class MurekaClient:
    """Async client. Construct one per app/worker; reuses an httpx.AsyncClient."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 2,
        retry_base_delay_s: float = 2.0,
    ) -> None:
        self.settings = settings or get_settings()
        self.max_retries = max_retries
        self.retry_base_delay_s = retry_base_delay_s
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.settings.mureka_api_base,
            timeout=self.settings.mureka_timeout_s,
            headers={
                "Authorization": f"Bearer {self.settings.mureka_api_key.get_secret_value()}",
                "Accept": "application/json",
                "User-Agent": "mureka-studio/0.1",
            },
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> MurekaClient:
        return self

    async def __aexit__(self, *_exc_info) -> None:
        await self.aclose()

    # ---------- core HTTP wrapper with retry ----------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        trace_id = get_trace_id() or "no-trace"
        headers = {"X-Trace-Id": trace_id}

        attempt = 0
        last_exc: Exception | None = None
        while attempt <= self.max_retries:
            attempt += 1
            try:
                response = await self._client.request(
                    method, path, json=json, params=params, headers=headers
                )
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                log.warning(
                    "mureka.transport_error",
                    method=method,
                    path=path,
                    attempt=attempt,
                    trace_id=trace_id,
                    error=str(exc),
                )
                if attempt > self.max_retries:
                    raise MurekaTransientError(
                        f"transport error: {exc}", code="transport_error"
                    ) from exc
                await asyncio.sleep(self.retry_base_delay_s * (2 ** (attempt - 1)))
                continue

            payload = _safe_json(response) if response.status_code >= 400 else None
            mureka_trace = _extract_trace_id(response, payload)
            log.info(
                "mureka.http",
                method=method,
                path=path,
                status=response.status_code,
                trace_id=trace_id,
                mureka_trace_id=mureka_trace,
                attempt=attempt,
            )

            if response.status_code < 400:
                return response

            if _retryable(response.status_code) and attempt <= self.max_retries:
                await asyncio.sleep(self.retry_base_delay_s * (2 ** (attempt - 1)))
                continue

            code, msg = _extract_error(payload, response.status_code)
            if not msg:
                msg = response.text[:200]
            if response.status_code < 500 and response.status_code != 429:
                raise MurekaPermanentError(
                    msg, code=code, status_code=response.status_code
                )
            # 5xx / 429 exhausted retries
            raise MurekaTransientError(msg, code=code, status_code=response.status_code)

        # exhausted without success
        raise MurekaTransientError(
            f"exhausted retries: {last_exc}", code="retries_exhausted"
        )

    # ---------- API methods ----------

    async def generate_lyrics(
        self, prompt: str, language: str = "ko", **extra: Any
    ) -> LyricsResult:
        """`POST /lyrics/generate` — synchronous within Mureka, ~few seconds."""
        body: dict[str, Any] = {"prompt": prompt, "language": language, **extra}
        response = await self._request("POST", "/lyrics/generate", json=body)
        data = response.json()
        lyrics = (
            data.get("lyrics")
            or data.get("text")
            or data.get("content")
            or (data.get("data", {}).get("lyrics") if isinstance(data.get("data"), dict) else None)
            or ""
        )
        return LyricsResult(
            lyrics=lyrics,
            language=data.get("language", language),
            raw=data,
        )

    async def generate_song(
        self,
        lyrics: str | None,
        prompt: str,
        model: str = "auto",
        length_s: int = 60,
        **extra: Any,
    ) -> TaskResponse:
        """`POST /song/generate` — returns task id; poll with `query_task`."""
        body: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "length_s": length_s,
            **extra,
        }
        if lyrics:
            body["lyrics"] = lyrics
        response = await self._request("POST", "/song/generate", json=body)
        return _parse_task_response(response)

    async def generate_instrumental(
        self,
        prompt: str,
        model: str = "auto",
        length_s: int = 60,
        **extra: Any,
    ) -> TaskResponse:
        body: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "length_s": length_s,
            **extra,
        }
        response = await self._request("POST", "/instrumental/generate", json=body)
        return _parse_task_response(response)

    async def query_task(self, task_id: str) -> MurekaTaskStatus:
        response = await self._request("GET", f"/task/{task_id}")
        data = response.json() if response.content else {}
        error_obj = data.get("error") if isinstance(data, dict) else None
        if isinstance(error_obj, dict):
            error_code = error_obj.get("code") or data.get("error_code")
            error_message = error_obj.get("message")
        else:
            error_code = data.get("error_code")
            error_message = data.get("error_message") or (
                error_obj if isinstance(error_obj, str) else None
            )
        return MurekaTaskStatus(
            task_id=data.get("task_id") or task_id,
            state=_normalise_state(data.get("state") or data.get("status")),  # type: ignore[arg-type]
            stage=data.get("stage"),
            progress=data.get("progress"),
            items=_parse_items(data),
            error_code=error_code,
            error_message=error_message,
            trace_id=_extract_trace_id(response, data if isinstance(data, dict) else None),
            raw=data,
        )

    async def download_audio(self, url: str) -> bytes:
        """Download a generated audio file. Uses a fresh client for non-API URLs."""
        # url may be an absolute CDN URL; bypass base_url
        async with httpx.AsyncClient(timeout=self.settings.mureka_timeout_s) as fresh:
            r = await fresh.get(url)
            r.raise_for_status()
            return r.content


def _safe_json(response: httpx.Response) -> dict[str, Any] | None:
    try:
        return response.json()
    except (ValueError, httpx.DecodingError):
        return None


def _parse_task_response(response: httpx.Response) -> TaskResponse:
    data = response.json() if response.content else {}
    return TaskResponse(
        task_id=data.get("task_id") or data.get("id") or "",
        state=_normalise_state(data.get("state") or data.get("status") or "pending"),
        trace_id=_extract_trace_id(response, data if isinstance(data, dict) else None),
    )
