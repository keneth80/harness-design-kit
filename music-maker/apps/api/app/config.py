"""Application settings (pydantic-settings v2)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised configuration. Loaded from env / `.env`.

    All secret-like fields use `SecretStr` so they never appear in logs unless
    explicitly unwrapped. NEVER expose Mureka API key in any response payload.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    service_name: str = "mureka-studio-api"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mureka_studio"
    alembic_database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/mureka_studio"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Storage
    storage_provider: Literal["minio", "s3"] = "minio"
    storage_endpoint: str = "http://localhost:9000"
    storage_region: str = "us-east-1"
    storage_bucket: str = "mureka-studio-dev"
    storage_access_key: SecretStr = SecretStr("minioadmin")
    storage_secret_key: SecretStr = SecretStr("minioadmin")
    storage_use_ssl: bool = False
    cdn_base_url: str = "http://localhost:9000/mureka-studio-dev"

    # Mureka — BACKEND ONLY
    mureka_api_base: str = "https://api.mureka.ai/v1"
    mureka_api_key: SecretStr = SecretStr("mk_replace_me")
    mureka_timeout_s: int = 30

    # Moderation
    openai_api_key: SecretStr = SecretStr("")
    moderation_enabled: bool = True

    # Auth (JWT)
    jwt_signing_key: SecretStr = SecretStr("replace-with-256-bit-random-secret")
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 14

    # Optional integrations
    google_oauth_client_id: str = ""
    google_oauth_client_secret: SecretStr = SecretStr("")
    stripe_secret_key: SecretStr = SecretStr("")
    stripe_webhook_secret: SecretStr = SecretStr("")

    # Observability
    sentry_dsn_api: str = ""
    otel_exporter_otlp_endpoint: str = ""

    # Worker tuning
    mureka_poll_interval_s: int = 5
    mureka_poll_max_count: int = 60
    generation_default_cost: int = Field(default=1, ge=0)

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
