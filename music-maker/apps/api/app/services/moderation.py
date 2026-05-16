"""Content moderation — OpenAI Moderation API (optional, env-gated)."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ModerationDecision:
    flagged: bool
    categories: tuple[str, ...] = ()


# Cheap keyword fallback when OpenAI key is absent (dev/test).
_BLOCKED_KEYWORDS = (
    "kill yourself",
    "child sexual",
    "csam",
)


async def check_text(text: str) -> ModerationDecision:
    """Moderate `text`. Returns flagged=False on errors (soft-fail) — but logs."""
    settings = get_settings()
    if not settings.moderation_enabled:
        return ModerationDecision(False)

    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        # Fallback heuristic
        lowered = text.lower()
        matches = tuple(kw for kw in _BLOCKED_KEYWORDS if kw in lowered)
        return ModerationDecision(flagged=bool(matches), categories=matches)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        resp = await client.moderations.create(input=text)
        result = resp.results[0]
        cats = tuple(
            name for name, flagged in result.categories.model_dump().items() if flagged
        )
        return ModerationDecision(flagged=bool(result.flagged), categories=cats)
    except Exception as exc:  # noqa: BLE001 — soft-fail moderation
        log.warning("moderation.error", error=str(exc))
        return ModerationDecision(False)
