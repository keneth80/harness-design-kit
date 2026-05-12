"""
JARVIS Browser Chatbot — FastAPI 엔트리포인트

TODO: Claude Code에서 아래 순서로 구현 요청
1. "FastAPI WebSocket 엔드포인트 구현해줘"
2. "BrowserManager 코어 모듈 구현해줘"
3. "LangGraph 라우터 구현해줘"
4. "Google Sheets 태스크 구현해줘"
5. "Meta Business 태스크 구현해줘"
6. "Telegram 알림 모듈 구현해줘"
"""

# from contextlib import asynccontextmanager
# from fastapi import FastAPI, WebSocket
# from .core.browser_manager import BrowserManager
# from .websocket.manager import WSManager

# TODO: 아래 구조로 구현
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     browser_mgr = BrowserManager()
#     await browser_mgr.connect_all()
#     yield
#     await browser_mgr.disconnect_all()
#
# app = FastAPI(lifespan=lifespan)
#
# @app.websocket("/ws/{user_id}")
# async def websocket_endpoint(ws: WebSocket, user_id: str): ...
#
# @app.get("/api/v1/services/status")
# async def service_status(): ...
