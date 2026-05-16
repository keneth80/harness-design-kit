"""FastAPI + SSE 기반 실시간 모니터링 대시보드."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from src.core.config import get_settings
from src.core.logger import get_logger
from src.dashboard.events import get_bus

_log = get_logger("dashboard")
_STATIC = Path(__file__).parent / "static"


@dataclass
class DashboardDeps:
    """대시보드가 조회할 런타임 의존성. 모두 optional — 없으면 해당 endpoint 빈 응답."""

    registry: object = None
    memory_store: object = None
    shared_memory: object = None
    session_search: object = None
    skill_manager: object = None


def create_app(deps: DashboardDeps | None = None) -> FastAPI:
    app = FastAPI(title="JARVIS Dashboard", docs_url=None, redoc_url=None)
    bus = get_bus()
    deps = deps or DashboardDeps()

    if _STATIC.exists():
        app.mount("/static", StaticFiles(directory=_STATIC), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        html = _STATIC / "index.html"
        if html.exists():
            return html.read_text(encoding="utf-8")
        return "<h1>JARVIS Dashboard</h1><p>static/index.html missing</p>"

    @app.get("/api/stats")
    async def stats() -> dict:
        return {
            "event_counts": bus.stats(),
            "buffered": len(bus.recent(limit=1000)),
        }

    @app.get("/api/events/recent")
    async def recent(limit: int = 50) -> list[dict]:
        return [ev.to_dict() for ev in bus.recent(limit=limit)]

    # ─── 사용자 패널 ─────────────────────────────────
    @app.get("/api/users")
    async def users_endpoint() -> list[dict]:
        if not deps.registry:
            return []
        out = []
        for u in deps.registry.list_users():
            mem_bytes = 0
            prof_bytes = 0
            session_count = 0
            try:
                if deps.memory_store:
                    mem_bytes = len(deps.memory_store.get_memory(u.user_id).encode("utf-8"))
                    prof_bytes = len(
                        deps.memory_store.get_user_profile(u.user_id).encode("utf-8")
                    )
            except Exception:
                pass
            try:
                if deps.session_search:
                    session_count = deps.session_search.count(u.user_id)
            except Exception:
                pass
            out.append(
                {
                    "user_id": u.user_id,
                    "display_name": u.display_name,
                    "role": u.role,
                    "is_minor": u.is_minor,
                    "telegram_id": u.telegram_id,
                    "memory_bytes": mem_bytes,
                    "profile_bytes": prof_bytes,
                    "session_messages": session_count,
                }
            )
        return out

    # ─── 감사 로그 ─────────────────────────────────
    @app.get("/api/audit/shared")
    async def audit_shared(limit: int = 20) -> list[dict]:
        if not deps.shared_memory:
            return []
        return deps.shared_memory.audit_tail(limit=limit)

    @app.get("/api/audit/skills")
    async def audit_skills(limit: int = 20) -> list[dict]:
        if not deps.skill_manager:
            return []
        return deps.skill_manager.audit_tail(limit=limit)

    @app.get("/api/skills")
    async def list_skills(user_id: str | None = None) -> list[dict]:
        if not deps.skill_manager:
            return []
        out = []
        for s in deps.skill_manager.list_skills(user_id=user_id):
            out.append(
                {
                    "name": s["name"],
                    "description": s.get("description", ""),
                    "tags": s.get("tags", []),
                    "adult_only": s.get("adult_only", False),
                }
            )
        return out

    @app.get("/events/stream")
    async def stream():
        async def gen():
            try:
                async for ev in bus.subscribe():
                    # named event 없이 default("message")로 보내야 EventSource.onmessage가 받음.
                    # data는 JSON 문자열로 명시 직렬화.
                    yield {"data": json.dumps(ev.to_dict(), ensure_ascii=False)}
            except asyncio.CancelledError:
                _log.info("sse client disconnected")
                raise

        return EventSourceResponse(gen())

    return app


async def serve() -> None:
    import uvicorn

    settings = get_settings()
    config = uvicorn.Config(
        create_app(),
        host="0.0.0.0",
        port=settings.dashboard_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    _log.info(f"dashboard → http://localhost:{settings.dashboard_port}")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(serve())
