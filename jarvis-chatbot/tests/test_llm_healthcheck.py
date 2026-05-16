"""LM Studio 헬스체크 integration test.

전제: LM Studio가 실행 중이고 .env의 LMSTUDIO_MODEL이 로드되어 있어야 한다.
실패 시 안내 메시지를 명확히 보여준다.
"""
from __future__ import annotations

import pytest

from src.core.config import get_settings
from src.core.llm import LMStudioClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lmstudio_healthcheck_returns_ok() -> None:
    settings = get_settings()
    client = LMStudioClient(settings)
    result = await client.healthcheck()

    assert result.ok, (
        f"\nLM Studio healthcheck FAILED\n"
        f"  base_url        : {result.base_url}\n"
        f"  target_model    : {result.target_model}\n"
        f"  available_models: {result.available_models}\n"
        f"  error           : {result.error}\n"
        f"\nCheck:\n"
        f"  1) LM Studio가 실행 중인지 (localhost:1234)\n"
        f"  2) .env의 LMSTUDIO_MODEL='{result.target_model}'이 로드되어 있는지\n"
        f"  3) LMSTUDIO_BASE_URL이 올바른지\n"
    )
    assert result.target_model in result.available_models
