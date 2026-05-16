"""환경 설정. .env를 자동 로드하고 타입 검증된 Settings 객체를 제공."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _runtime_root() -> Path:
    """PyInstaller --onefile 시 바이너리 옆 디렉토리, dev에서는 프로젝트 루트."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _runtime_root()


def _env_candidates() -> tuple[Path, ...]:
    """cwd → binary_dir 순서로 .env 검색. 둘 다 있으면 cwd가 우선(나중에 머지)."""
    seen: list[Path] = []
    for p in (PROJECT_ROOT / ".env", Path.cwd() / ".env"):
        if p not in seen:
            seen.append(p)
    return tuple(seen)


def _default_data_dir() -> Path:
    """frozen이면 cwd/data, dev면 프로젝트 루트의 data."""
    return Path.cwd() / "data" if getattr(sys, "frozen", False) else PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_candidates(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    lmstudio_base_url: str = Field(
        default="http://localhost:1234/v1", alias="LMSTUDIO_BASE_URL"
    )
    lmstudio_model: str = Field(default="gemma-4-26b-a4b-it", alias="LMSTUDIO_MODEL")
    lmstudio_api_key: str = Field(default="lm-studio", alias="LMSTUDIO_API_KEY")

    dashboard_port: int = Field(default=3800, alias="DASHBOARD_PORT")
    data_dir: Path = Field(default_factory=_default_data_dir, alias="DATA_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    rag_top_k: int = Field(default=3, alias="RAG_TOP_K")
    rag_score_threshold: float = Field(default=0.3, alias="RAG_SCORE_THRESHOLD")
    context_window_turns: int = Field(default=10, alias="CONTEXT_WINDOW_TURNS")

    @field_validator("lmstudio_base_url")
    @classmethod
    def _ensure_v1_suffix(cls, v: str) -> str:
        v = v.rstrip("/")
        if not v.endswith("/v1"):
            v = f"{v}/v1"
        return v

    @field_validator("data_dir")
    @classmethod
    def _resolve_data_dir(cls, v: Path) -> Path:
        return v if v.is_absolute() else (Path.cwd() / v).resolve()

    @property
    def allowed_user_ids(self) -> list[int]:
        """TELEGRAM_CHAT_ID를 콤마 구분 → int 리스트로 파싱. 빈 값이면 빈 리스트."""
        raw = self.telegram_chat_id.strip()
        if not raw:
            return []
        return [int(x.strip()) for x in raw.split(",") if x.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def _mask(s: str, keep: int = 4) -> str:
    if not s:
        return "(empty)"
    if len(s) <= keep:
        return "*" * len(s)
    return s[:keep] + "*" * (len(s) - keep)


if __name__ == "__main__":
    s = get_settings()
    print("=== Jarvis Settings ===")
    print(f"telegram_bot_token   = {_mask(s.telegram_bot_token)}")
    print(f"telegram_chat_id     = {s.telegram_chat_id}  (parsed: {s.allowed_user_ids})")
    print(f"lmstudio_base_url    = {s.lmstudio_base_url}")
    print(f"lmstudio_model       = {s.lmstudio_model}")
    print(f"lmstudio_api_key     = {_mask(s.lmstudio_api_key)}")
    print(f"dashboard_port       = {s.dashboard_port}")
    print(f"data_dir             = {s.data_dir}")
    print(f"log_level            = {s.log_level}")
    print(f"rag_top_k            = {s.rag_top_k}")
    print(f"rag_score_threshold  = {s.rag_score_threshold}")
    print(f"context_window_turns = {s.context_window_turns}")
