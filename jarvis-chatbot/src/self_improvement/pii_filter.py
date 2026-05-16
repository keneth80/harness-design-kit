"""PII / Credential 결정론적 마스킹.

Level:
  - 'personal' : 거의 그대로 (자기 메모리 — 본인만 보므로 마스킹 최소)
  - 'shared'   : API 키·토큰·주민번호만 마스킹 (가족 공유)
  - 'skill'    : 모두 마스킹 (전역 공유)

LLM 보조 익명화는 Phase 5에서 결합.
"""
from __future__ import annotations

import re
from typing import Literal

Level = Literal["personal", "shared", "skill"]


# 카테고리별 패턴
_PATTERNS: dict[str, list[re.Pattern]] = {
    "api_key": [
        re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),  # OpenAI/Anthropic 류
        re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
        re.compile(r"AIza[A-Za-z0-9_\-]{35}"),  # Google
        re.compile(r"ghp_[A-Za-z0-9]{36}"),  # GitHub PAT
        re.compile(r"github_pat_[A-Za-z0-9_]{22,}"),
        re.compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}"),  # Slack
        re.compile(r"hf_[A-Za-z0-9]{20,}"),  # HuggingFace
        re.compile(r"fal_[A-Za-z0-9_\-]{20,}"),  # fal.ai
    ],
    "telegram_token": [
        re.compile(r"\d{9,10}:[A-Za-z0-9_\-]{35}"),
    ],
    "rrn": [  # 주민등록번호
        re.compile(r"\b\d{6}-?[1-4]\d{6}\b"),
    ],
    "card_number": [
        re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    ],
    "korean_phone": [
        re.compile(r"\b01[0-9][-.\s]?\d{3,4}[-.\s]?\d{4}\b"),
    ],
    "email": [
        re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    ],
}


# 레벨별 적용 카테고리
_LEVEL_CATEGORIES: dict[Level, tuple[str, ...]] = {
    "personal": ("api_key", "telegram_token", "rrn"),
    "shared": ("api_key", "telegram_token", "rrn", "card_number"),
    "skill": (
        "api_key",
        "telegram_token",
        "rrn",
        "card_number",
        "korean_phone",
        "email",
    ),
}


def clean(text: str, *, level: Level = "shared") -> str:
    if not text:
        return text
    out = text
    for cat in _LEVEL_CATEGORIES[level]:
        token = f"<{cat.upper()}_REDACTED>"
        for pat in _PATTERNS[cat]:
            out = pat.sub(token, out)
    return out


def detect(text: str, *, level: Level = "shared") -> dict[str, int]:
    """카테고리별 매치 수. 디버그/감사용."""
    counts: dict[str, int] = {}
    for cat in _LEVEL_CATEGORIES[level]:
        n = 0
        for pat in _PATTERNS[cat]:
            n += len(pat.findall(text))
        if n:
            counts[cat] = n
    return counts
