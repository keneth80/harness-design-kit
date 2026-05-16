"""LM Studio (OpenAI 호환) 비동기 클라이언트."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from openai import AsyncOpenAI
from openai import APIConnectionError, APIStatusError

from src.core.config import Settings, get_settings
from src.core.logger import get_logger


@dataclass(frozen=True)
class HealthcheckResult:
    ok: bool
    base_url: str
    target_model: str
    available_models: list[str]
    error: str | None = None

    def summary(self) -> str:
        if self.ok:
            return f"OK | model={self.target_model} | available={len(self.available_models)}"
        return f"FAIL | {self.error}"


class LMStudioClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = AsyncOpenAI(
            base_url=self._settings.lmstudio_base_url,
            api_key=self._settings.lmstudio_api_key,
        )
        self._log = get_logger("llm")

    @property
    def model(self) -> str:
        return self._settings.lmstudio_model

    async def healthcheck(self) -> HealthcheckResult:
        """`/v1/models`를 호출해 LM Studio 응답과 타겟 모델 로드 여부를 검증."""
        trace_id = uuid.uuid4().hex[:8]
        log = self._log.bind(trace_id=trace_id)
        log.info(f"healthcheck → {self._settings.lmstudio_base_url}")
        try:
            resp = await self._client.models.list()
            ids = [m.id for m in resp.data]
            ok = self._settings.lmstudio_model in ids
            if not ok:
                log.warning(
                    f"target model '{self._settings.lmstudio_model}' not in {ids}"
                )
            return HealthcheckResult(
                ok=ok,
                base_url=self._settings.lmstudio_base_url,
                target_model=self._settings.lmstudio_model,
                available_models=ids,
                error=None if ok else f"model '{self._settings.lmstudio_model}' not loaded",
            )
        except APIConnectionError as e:
            log.error(f"connection error: {e}")
            return HealthcheckResult(
                ok=False,
                base_url=self._settings.lmstudio_base_url,
                target_model=self._settings.lmstudio_model,
                available_models=[],
                error=f"connection error: {e}",
            )
        except APIStatusError as e:
            log.error(f"status error: {e.status_code} {e.message}")
            return HealthcheckResult(
                ok=False,
                base_url=self._settings.lmstudio_base_url,
                target_model=self._settings.lmstudio_model,
                available_models=[],
                error=f"status {e.status_code}: {e.message}",
            )

    async def chat(
        self,
        messages: Iterable[dict[str, str]],
        *,
        temperature: float = 0.7,
        json_mode: bool = False,
        trace_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        tid = trace_id or uuid.uuid4().hex[:8]
        log = self._log.bind(trace_id=tid)
        log.info(f"chat → model={self.model} json={json_mode}")
        params: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if json_mode:
            params["response_format"] = {"type": "json_object"}
        params.update(kwargs)
        resp = await self._client.chat.completions.create(**params)
        content = resp.choices[0].message.content or ""
        log.info(f"chat ← len={len(content)}")
        return content


async def _main() -> None:
    client = LMStudioClient()
    result = await client.healthcheck()
    print(result.summary())
    if result.ok:
        reply = await client.chat(
            [{"role": "user", "content": "안녕. 한 문장으로 자기소개해."}],
            temperature=0.3,
        )
        print(f"reply: {reply}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
