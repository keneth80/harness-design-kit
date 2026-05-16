"""텔레그램 봇 빌더. main.py에서 폴링 실행."""
from __future__ import annotations

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.core.config import get_settings
from src.core.logger import get_logger
from src.telegram.handlers import HandlerState, make_handlers

_log = get_logger("telegram.bot")


def build_application(state: HandlerState) -> Application:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN이 비어있습니다. .env를 확인하세요.")

    app = Application.builder().token(settings.telegram_bot_token).build()
    h = make_handlers(state)
    app.add_handler(CommandHandler("start", h["start"]))
    app.add_handler(CommandHandler("reset", h["reset"]))
    app.add_handler(CommandHandler("history", h["history"]))
    app.add_handler(CommandHandler("status", h["status"]))
    app.add_handler(CommandHandler("mode", h["mode"]))
    app.add_handler(CommandHandler("ingest", h["ingest"]))
    app.add_handler(CommandHandler("myid", h["myid"]))
    app.add_handler(CommandHandler("users", h["users"]))
    app.add_handler(CommandHandler("adduser", h["adduser"]))
    app.add_handler(CommandHandler("removeuser", h["removeuser"]))
    app.add_handler(CommandHandler("help", h["help"]))
    app.add_handler(CommandHandler("rag_help", h["rag_help"]))
    app.add_handler(CommandHandler("ingest_help", h["ingest_help"]))
    app.add_handler(CommandHandler("memory", h["memory"]))
    app.add_handler(CommandHandler("profile", h["profile"]))
    app.add_handler(CommandHandler("forget", h["forget"]))
    app.add_handler(CommandHandler("share", h["share"]))
    app.add_handler(CommandHandler("shared", h["shared"]))
    app.add_handler(CommandHandler("audit", h["audit"]))
    app.add_handler(CommandHandler("skills", h["skills"]))
    app.add_handler(CommandHandler("docs", h["docs"]))
    app.add_handler(CommandHandler("doc", h["doc"]))
    app.add_handler(CommandHandler("preview", h["preview"]))
    app.add_handler(CommandHandler("getdoc", h["getdoc"]))
    app.add_handler(CommandHandler("deldoc", h["deldoc"]))
    app.add_handler(MessageHandler(filters.Document.ALL, h["ingest"]))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h["message"]))
    _log.info("telegram application built")
    return app
