"""Config 단위 테스트. .env 의존 없이 환경변수만 주입."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.core.config import Settings, get_settings


def _make(env: dict[str, str]) -> Settings:
    # pydantic-settings는 환경변수를 우선 사용하므로 monkeypatch 흉내
    backup = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        return Settings(_env_file=None)  # type: ignore[call-arg]
    finally:
        for k, v in backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_base_url_appends_v1_suffix() -> None:
    s = _make({"LMSTUDIO_BASE_URL": "http://localhost:1234"})
    assert s.lmstudio_base_url == "http://localhost:1234/v1"


def test_base_url_preserves_v1_suffix() -> None:
    s = _make({"LMSTUDIO_BASE_URL": "http://localhost:5000/v1"})
    assert s.lmstudio_base_url == "http://localhost:5000/v1"


def test_base_url_strips_trailing_slash() -> None:
    s = _make({"LMSTUDIO_BASE_URL": "http://localhost:1234/"})
    assert s.lmstudio_base_url == "http://localhost:1234/v1"


def test_allowed_user_ids_empty() -> None:
    s = _make({"TELEGRAM_CHAT_ID": ""})
    assert s.allowed_user_ids == []


def test_allowed_user_ids_single() -> None:
    s = _make({"TELEGRAM_CHAT_ID": "12345"})
    assert s.allowed_user_ids == [12345]


def test_allowed_user_ids_csv() -> None:
    s = _make({"TELEGRAM_CHAT_ID": "1, 2,3 , 4"})
    assert s.allowed_user_ids == [1, 2, 3, 4]


def test_data_dir_resolved_absolute() -> None:
    s = _make({"DATA_DIR": "./data"})
    assert s.data_dir.is_absolute()


def test_get_settings_cached() -> None:
    assert get_settings() is get_settings()
