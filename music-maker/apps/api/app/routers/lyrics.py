"""/api/v1/lyrics — synchronous AI lyric generation."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.exceptions import ModerationBlockedError
from app.deps import get_current_user
from app.models.user import User
from app.schemas.lyrics import (
    LyricsGenerateRequest,
    LyricsGenerateResponse,
    ModerationResult,
)
from app.services import moderation
from app.services.mureka_client import MurekaClient

router = APIRouter(prefix="/api/v1/lyrics", tags=["lyrics"])


@router.post("/generate", response_model=LyricsGenerateResponse)
async def generate_lyrics(
    body: LyricsGenerateRequest,
    _user: User = Depends(get_current_user),
) -> LyricsGenerateResponse:
    # input moderation
    decision = await moderation.check_text(body.topic)
    if decision.flagged:
        raise ModerationBlockedError(
            detail="topic blocked by moderation",
            categories=list(decision.categories),
        )

    async with MurekaClient() as client:
        result = await client.generate_lyrics(prompt=body.topic, language=body.language)

    # output moderation
    out_decision = await moderation.check_text(result.lyrics)
    if out_decision.flagged:
        raise ModerationBlockedError(
            detail="generated lyrics blocked by moderation",
            categories=list(out_decision.categories),
        )

    return LyricsGenerateResponse(
        lyrics=result.lyrics,
        moderation=ModerationResult(
            flagged=False,
            categories=list(out_decision.categories),
        ),
        credit_cost=0,
    )
