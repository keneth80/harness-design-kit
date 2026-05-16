"""JARVIS 진입점. 텔레그램 봇 + 대시보드 동시 실행."""
from __future__ import annotations

import asyncio
import signal
import sys

import uvicorn

from src.agents.supervisor import build_graph
from src.core.config import get_settings
from src.core.llm import LMStudioClient
from src.core.logger import get_logger
from src.dashboard.server import DashboardDeps, create_app
from src.memory.long_term import LongTermMemory
from src.memory.rag_store import RagStore
from src.memory.short_term import ContextBuilder
from src.self_improvement.context_loader import ContextLoader
from src.self_improvement.memory_store import MemoryStore
from src.self_improvement.reflection import ReflectionEngine
from src.self_improvement.session_search import SessionSearch
from src.self_improvement.shared_memory import SharedMemoryStore
from src.self_improvement.skill_manager import SkillManager
from src.self_improvement.user_registry import get_registry
from src.telegram.bot import build_application
from src.telegram.handlers import HandlerState

_log = get_logger("main")


async def _bootstrap():
    settings = get_settings()
    _log.info(f"JARVIS booting … model={settings.lmstudio_model}")

    client = LMStudioClient()
    hc = await client.healthcheck()
    _log.info(f"healthcheck: {hc.summary()}")
    if not hc.ok:
        _log.warning(f"LM Studio not ready: {hc.error}. 봇은 시작하지만 응답 시 실패합니다.")

    memory = LongTermMemory()
    await memory.init()
    store = RagStore()
    ctx_builder = ContextBuilder(memory)
    graph = build_graph(client, store)

    # Self-improvement layer
    registry = get_registry()
    _log.info(f"registry: users={len(registry.list_users())}")
    memory_store = MemoryStore(settings.data_dir, registry=registry)
    shared_memory = SharedMemoryStore(settings.data_dir, registry=registry)
    session_search = SessionSearch(settings.data_dir, registry=registry)
    skill_manager = SkillManager(settings.data_dir, client=client, registry=registry)
    context_loader = ContextLoader(memory_store, registry=registry)
    context_loader.attach_shared_memory(shared_memory)
    context_loader.attach_session_search(session_search)
    context_loader.attach_skill_manager(skill_manager)
    reflection = ReflectionEngine(
        memory_store, client, registry=registry, skill_manager=skill_manager
    )

    state = HandlerState(
        graph=graph,
        memory=memory,
        store=store,
        ctx_builder=ctx_builder,
        client=client,
        registry=registry,
        memory_store=memory_store,
        context_loader=context_loader,
        shared_memory=shared_memory,
        session_search=session_search,
        reflection=reflection,
        skill_manager=skill_manager,
    )
    return state


async def _run_dashboard(deps: DashboardDeps) -> None:
    settings = get_settings()
    config = uvicorn.Config(
        create_app(deps),
        host="0.0.0.0",
        port=settings.dashboard_port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    _log.info(f"📊 dashboard → http://localhost:{settings.dashboard_port}")
    await server.serve()


async def _run_telegram(state: HandlerState) -> None:
    app = build_application(state)
    _log.info("🤖 telegram polling 시작")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


async def main() -> None:
    state = await _bootstrap()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    async def _watch_stop(tasks: list[asyncio.Task]) -> None:
        await stop_event.wait()
        _log.info("종료 신호 수신")
        for t in tasks:
            t.cancel()

    deps = DashboardDeps(
        registry=state.registry,
        memory_store=state.memory_store,
        shared_memory=state.shared_memory,
        session_search=state.session_search,
        skill_manager=state.skill_manager,
    )
    tg_task = asyncio.create_task(_run_telegram(state), name="telegram")
    dash_task = asyncio.create_task(_run_dashboard(deps), name="dashboard")
    watcher = asyncio.create_task(_watch_stop([tg_task, dash_task]), name="watcher")

    try:
        await asyncio.gather(tg_task, dash_task, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    finally:
        watcher.cancel()
        _log.info("JARVIS 종료")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
