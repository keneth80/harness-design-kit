"""loguru 기반 구조화 로깅. trace_id 슬롯과 파일 rotation을 제공."""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from src.core.config import get_settings

_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "<level>{level: <7}</level> "
    "<cyan>{extra[trace_id]}</cyan> "
    "<blue>{name}:{function}:{line}</blue> "
    "<level>{message}</level>"
)

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return

    settings = get_settings()
    logger.remove()
    logger.configure(extra={"trace_id": "-"})
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=_FORMAT,
        backtrace=False,
        diagnose=False,
    )
    log_dir: Path = settings.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "jarvis.log",
        level=settings.log_level,
        format=_FORMAT,
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
    )
    _configured = True


def get_logger(name: str | None = None, *, trace_id: str | None = None):
    _configure()
    bound = logger.bind(trace_id=trace_id or "-")
    return bound.opt(depth=0) if name is None else bound


if __name__ == "__main__":
    log = get_logger(trace_id="test-001")
    log.info("logger smoke test")
    log.warning("warn level")
    log.error("error level")
