"""텔레그램 명령어 핸들러. supervisor 호출과 상태 관리."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from src.core.config import get_settings
from src.core.llm import LMStudioClient
from src.core.logger import get_logger
from src.dashboard.events import get_bus
from src.memory.long_term import LongTermMemory
from src.memory.rag_store import RagStore
from src.memory.short_term import ContextBuilder, SYSTEM_PROMPT_DEFAULT
from src.self_improvement.context_loader import ContextLoader
from src.self_improvement.memory_store import MemoryStore
from src.self_improvement.reflection import ReflectionEngine
from src.self_improvement.session_search import SessionSearch
from src.self_improvement.shared_memory import SharedMemoryStore
from src.self_improvement.skill_manager import SkillManager
from src.self_improvement.user_registry import (
    UnauthorizedError,
    User,
    UserRegistry,
)

_log = get_logger("telegram")
_bus = get_bus()
_MAX_TG_LEN = 4096


_HELP_GENERAL = """🤖 JARVIS 명령어

기본
  /start          새 세션 시작 (직전 세션은 자동 요약)
  /reset          컨텍스트 초기화
  /history        최근 20개 메시지
  /status         내 권한·모델·문서 수·모드 확인
  /myid           내 텔레그램 user_id 확인

라우팅
  /mode chat|rag|auto   응답 경로 강제. 기본 auto (LLM이 결정)

RAG (지식 검색)
  /ingest <경로>  또는 파일 첨부 + /ingest
  /docs           ingest된 문서 목록
  /doc <파일명>   추출된 본문 텍스트 보기
  /preview <파일명> [N=3] [start=1]  PDF 페이지를 이미지로 미리보기
  /getdoc <파일명> 원본 파일 다운로드 (텔레그램으로 다시 보냄)
  /deldoc <파일명> 본인 권한 범위에서 삭제 (Chroma + 디스크)
  /rag_help       RAG 사용법 자세히
  /ingest_help    /ingest 자세히

메모리 (본인 전용)
  /memory         내 MEMORY.md 보기
  /profile        내 USER.md 보기
  /forget <키워드>  본인 메모리에서 키워드 포함 라인 제거

공유 메모리 (가족용)
  /shared         가족 공유 메모리 보기 (미성년자는 비어있음)
  /share <사실>   [admin] 가족 공유 메모리에 추가 (PII 자동 마스킹)

Skill (전역, PII 자동 마스킹)
  /skills         사용 가능한 skill 목록 (미성년자는 adult_only 제외)

관리자 (admin 전용)
  /users          허용 목록
  /adduser <tg_id> [--alias name] [--minor] [메모]
                  또는 포워드+/adduser [...옵션...]
  /removeuser <user_id 또는 tg_id>
  /audit          공유 메모리 감사 로그 (최근 20건)

도움말
  /help           이 화면
"""


_HELP_RAG = """🔍 RAG (Retrieval-Augmented Generation) 사용법

▍ 1단계 — 문서 추가 (/ingest)

방법 A. 파일 첨부 (편함)
  텔레그램에서 .txt/.md 파일을 첨부 → 캡션 또는 직후에 /ingest

방법 B. 경로 지정 (서버 로컬 파일)
  /ingest /full/path/note.md

저장 위치는 권한에 따라 자동:
  • admin → 공유 컬렉션 (모든 멤버가 검색 가능)
  • member → 본인 개인 컬렉션 (본인만 검색)

▍ 2단계 — 질문

그냥 평소대로 질문하면 LLM 라우터가 자동 결정:
  • "문서에 따르면…", "내 노트에…" → 자동 RAG
  • 잡담·일반 상식 → 그냥 chat

강제 지정:
  /mode rag    모든 질문 RAG로
  /mode chat   모든 질문 chat으로 (검색 생략)
  /mode auto   기본값 복귀

▍ 3단계 — 결과 확인

  • 봇 답변 끝에 [1], [2] 인용 마커
  • 대시보드(http://localhost:3800)의
    🔍 최근 RAG 결과 패널에 출처·점수 표시
    🌐 shared = 공유, 👤 <id> = 그 사용자 개인

▍ 지원 형식

  ✅ .txt .md .csv .py .json 등 평문
  ❌ .pdf .docx .hwp (현재 미지원 — 별도 추출기 필요)

▍ 청크(chunk) 단위

문서는 500자 단위로 잘게 쪼개져 저장됨 (overlap 50자).
/status 의 'shared=N'은 파일 수가 아니라 청크 수.
"""


_HELP_INGEST = """📥 /ingest 자세히

▍ 사용법

1) 파일 첨부 + /ingest
   .txt/.md 등 텍스트 파일을 메시지에 첨부 후
   /ingest 또는 캡션에 /ingest 입력

2) 경로 지정
   /ingest /path/to/file.md
   /ingest ~/notes/diary.md   (~ 확장 됨)

▍ 응답 예시

  📥 ingested filename.md: chunks=12 (공유 → jarvis_docs)
  📥 ingested diary.md: chunks=5 (개인 → jarvis_docs_user_109494677)

  • chunks: 잘려서 저장된 청크 개수
  • (...): 어느 컬렉션에 들어갔는지

▍ 권한별 동작

  admin (.env TELEGRAM_CHAT_ID에 있는 사람)
    → 공유 컬렉션 (jarvis_docs)에 저장
    → 모든 사용자가 검색에서 볼 수 있음

  member (관리자가 /adduser로 추가한 사람)
    → 본인 전용 컬렉션 (jarvis_docs_user_<id>)
    → 본인만 검색 가능, 다른 멤버는 못 봄

▍ 파일 보관

  업로드된 원본 파일은 data/documents/ 아래 저장됨
    shared/ — admin 업로드
    user_<id>/ — 멤버 업로드

▍ 같은 source 재업로드

  source 식별자가 같으면 (보통 파일경로) upsert 됩니다.
  즉 같은 파일을 두 번 /ingest 하면 청크가 덮어쓰기 됨.
  파일을 수정한 뒤 다시 올리면 자동 갱신.

▍ 지원 형식

  ✅ 평문: .txt .md .csv .json .py .yml .html .log .sql .sh 등
  ✅ PDF: .pdf (pypdf로 페이지별 텍스트 추출)
  ✅ Word: .docx (단락 + 표 셀)
  ❌ .doc (구 Word), .hwp (한컴) — 미지원

▍ 주의

  • 스캔 PDF(이미지)는 OCR 미적용이라 텍스트 0
  • 표가 많은 docx는 셀이 'a | b | c' 형식으로 추출됨
  • 너무 짧은 메모(50자 미만)는 청크가 1개만 생기며 RAG 효과 낮음
  • 임베딩 모델은 한국어 우선 (jhgan/ko-sroberta-multitask)
"""


class HandlerState:
    """런타임 의존성 묶음. main.py에서 주입."""

    def __init__(
        self,
        *,
        graph: Any,
        memory: LongTermMemory,
        store: RagStore,
        ctx_builder: ContextBuilder,
        client: LMStudioClient,
        registry: UserRegistry,
        memory_store: MemoryStore,
        context_loader: ContextLoader,
        shared_memory: SharedMemoryStore,
        session_search: SessionSearch,
        reflection: ReflectionEngine,
        skill_manager: SkillManager,
    ) -> None:
        self.graph = graph
        self.memory = memory
        self.store = store
        self.ctx_builder = ctx_builder
        self.client = client
        self.registry = registry
        self.memory_store = memory_store
        self.context_loader = context_loader
        self.shared_memory = shared_memory
        self.session_search = session_search
        self.reflection = reflection
        self.skill_manager = skill_manager
        self.sessions: dict[str, str] = {}  # canonical user_id → session_id
        self.force_mode: dict[str, str] = {}  # canonical user_id → "chat"|"rag"|""


def _resolve(state: HandlerState, update: Update) -> User | None:
    """telegram id → registry User. 미등록 → None."""
    if not update.effective_user:
        return None
    return state.registry.by_telegram_id(update.effective_user.id)


def _is_admin(state: HandlerState, update: Update) -> bool:
    user = _resolve(state, update)
    return bool(user and user.role == "admin")


async def _allowed(state: HandlerState, update: Update) -> bool:
    user = _resolve(state, update)
    if user is not None:
        return True
    tg_id = update.effective_user.id if update.effective_user else None
    uname = update.effective_user.username if update.effective_user else None
    _log.warning(f"DENIED tg_id={tg_id} username={uname}")
    _bus.publish(
        "telegram.denied",
        {"telegram_id": tg_id, "username": uname},
    )
    return False


async def _close_and_summarize(
    state: HandlerState, session_id: str, user_id: str
) -> str | None:
    """현재 세션을 요약 후 종료. 메시지가 부족하면 요약 없이 종료."""
    summary = await state.memory.generate_summary(session_id, state.client)
    if summary:
        _bus.publish(
            "memory.summary",
            {"user_id": user_id, "session_id": session_id, "len": len(summary)},
        )
    await state.memory.end_session(session_id)
    return summary


async def _ensure_session(state: HandlerState, user_id: str) -> tuple[str, str | None]:
    if user_id in state.sessions:
        return state.sessions[user_id], None
    prior = await state.memory.latest_session(user_id)
    prior_summary = prior.summary if prior else None
    # 직전 세션에 메시지는 있는데 요약이 없으면 생성 시도
    if prior and not prior_summary:
        prior_summary = await state.memory.generate_summary(prior.id, state.client)
    sid = await state.memory.start_session(user_id)
    state.sessions[user_id] = sid
    return sid, prior_summary


async def _send(update: Update, text: str) -> None:
    for i in range(0, len(text), _MAX_TG_LEN):
        await update.effective_chat.send_message(text[i : i + _MAX_TG_LEN])


def make_handlers(state: HandlerState):
    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return await _send(update, "🚫 허용되지 않은 사용자입니다.")
        user = _resolve(state, update)
        uid = user.user_id
        # 직전 세션이 있다면 요약 후 종료
        old = state.sessions.pop(uid, None)
        if old:
            await _close_and_summarize(state, old, uid)
        # 새 세션
        sid = await state.memory.start_session(uid)
        state.sessions[uid] = sid
        _bus.publish("telegram.start", {"user_id": uid, "session_id": sid})
        await _send(
            update,
            f"🤖 JARVIS 시작. ({user.display_name}님)\n"
            "주요 명령: /reset /history /status /mode chat|rag|auto /ingest\n"
            "메모리: /memory /profile /forget\n"
            "도움말: /help  /rag_help  /ingest_help",
        )

    async def reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        uid = _resolve(state, update).user_id
        old = state.sessions.pop(uid, None)
        summary = None
        if old:
            summary = await _close_and_summarize(state, old, uid)
        state.force_mode.pop(uid, None)
        tail = f"\n📝 직전 세션 요약 저장됨 ({len(summary)}자)" if summary else ""
        await _send(update, f"♻️ 컨텍스트 초기화 완료. 새 세션 시작.{tail}")

    async def history(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        uid = _resolve(state, update).user_id
        sid = state.sessions.get(uid)
        if not sid:
            return await _send(update, "활성 세션이 없습니다. /start")
        msgs = await state.memory.get_session_messages(sid, limit=20)
        if not msgs:
            return await _send(update, "(빈 세션)")
        lines = [f"[{m.role}] {m.content[:200]}" for m in msgs]
        await _send(update, "\n".join(lines))

    async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        settings = get_settings()
        user = _resolve(state, update)
        uid = user.user_id
        mode = state.force_mode.get(uid, "auto")
        is_admin = user.role == "admin"
        shared = state.store.count_shared()
        personal = 0 if is_admin else state.store.count_for_user(uid)
        role = "admin" if is_admin else ("minor" if user.is_minor else "member")
        lines = [
            f"👤 {user.display_name} (user_id={uid}, role={role})",
            f"🔧 model = {settings.lmstudio_model}",
            f"📚 rag_docs: shared={shared}" + (f", personal={personal}" if not is_admin else ""),
            f"🎚 mode = {mode}",
            f"📊 dashboard: http://localhost:{settings.dashboard_port}",
        ]
        await _send(update, "\n".join(lines))

    async def mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        uid = _resolve(state, update).user_id
        arg = (ctx.args[0].lower() if ctx.args else "").strip()
        if arg not in ("chat", "rag", "auto"):
            return await _send(update, "사용법: /mode chat|rag|auto")
        if arg == "auto":
            state.force_mode.pop(uid, None)
        else:
            state.force_mode[uid] = arg
        await _send(update, f"🎚 mode = {arg}")

    async def ingest(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        from src.memory.text_extractor import UnsupportedFileError

        user = _resolve(state, update)
        owner_id = user.user_id
        is_admin = user.role == "admin"
        scope = "공유" if is_admin else "개인"
        # 첨부파일 또는 인자 경로
        doc = None
        if update.message and update.message.document:
            doc = update.message.document
        if doc:
            file = await ctx.bot.get_file(doc.file_id)
            # owner별 디렉토리에 저장
            sub = "shared" if is_admin else f"user_{owner_id}"
            target = (
                Path(get_settings().data_dir)
                / "documents"
                / sub
                / doc.file_name
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            await file.download_to_drive(target)
            try:
                n, coll = state.store.ingest_file_for(
                    target, owner_id=owner_id, is_admin=is_admin
                )
            except UnsupportedFileError as e:
                return await _send(update, f"❌ {e}")
            return await _send(
                update,
                f"📥 ingested {doc.file_name}: chunks={n} ({scope} → {coll})",
            )
        if ctx.args:
            path = Path(" ".join(ctx.args)).expanduser()
            if not path.exists():
                return await _send(update, f"❌ not found: {path}")
            try:
                n, coll = state.store.ingest_file_for(
                    path, owner_id=owner_id, is_admin=is_admin
                )
            except UnsupportedFileError as e:
                return await _send(update, f"❌ {e}")
            return await _send(
                update,
                f"📥 ingested {path.name}: chunks={n} ({scope} → {coll})",
            )
        await _send(update, "사용법: 파일 첨부 + /ingest  또는  /ingest <경로>")

    async def message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        if not update.message or not update.message.text:
            return
        user = _resolve(state, update)
        uid = user.user_id
        user_text = update.message.text.strip()
        if not user_text:
            return
        sid, prior_summary = await _ensure_session(state, uid)
        force = state.force_mode.get(uid, "")
        _bus.publish(
            "telegram.message",
            {"user_id": uid, "len": len(user_text), "force": force or None},
        )
        await update.effective_chat.send_action(ChatAction.TYPING)

        # 사용자별 system prompt (USER.md + MEMORY.md + ... 주입)
        system_prompt = state.context_loader.build_system_prompt(
            user_id=uid,
            base_prompt=SYSTEM_PROMPT_DEFAULT,
            user_message=user_text,
        )
        messages = await state.ctx_builder.build(
            session_id=sid,
            user_message=user_text,
            prior_summary=prior_summary,
            system_prompt_override=system_prompt,
        )
        graph_state = {
            "messages": messages,
            "user_id": uid,
            "is_admin": user.role == "admin",
            "session_id": sid,
            "user_message": user_text,
            "force_mode": force,
        }
        config = {"configurable": {"thread_id": sid}}
        result: dict[str, Any] = {}
        try:
            result = await state.graph.ainvoke(graph_state, config=config)
            reply = result.get("reply", "(빈 응답)")
        except Exception as e:
            _log.error(f"graph error: {e}")
            _bus.publish("agent.error", {"node": "supervisor", "error": str(e)})
            reply = f"⚠️ 오류: {e}"

        await state.memory.add_message(
            session_id=sid, user_id=uid, role="user", content=user_text
        )
        await state.memory.add_message(
            session_id=sid,
            user_id=uid,
            role="assistant",
            content=reply,
            metadata={"route": result.get("route")},
        )
        # FTS5 인덱스에도 저장 (검색용)
        try:
            state.session_search.save_message(
                uid, session_id=sid, role="user", content=user_text
            )
            state.session_search.save_message(
                uid, session_id=sid, role="assistant", content=reply
            )
        except Exception as e:
            _log.warning(f"fts save failed uid={uid}: {e}")

        # 자성 카운터 증가 + 백그라운드 reflection (다른 사용자 차단 안 함)
        state.reflection.increment(uid)
        recent = await state.memory.get_session_messages(sid, limit=40)
        conv = [
            {"role": m.role, "content": m.content}
            for m in recent
            if m.role in ("user", "assistant")
        ]
        asyncio.create_task(state.reflection.maybe_reflect(uid, conv))

        await _send(update, reply)

    # ─── 사용자 관리 (admin only) ─────────────────────────────────
    async def myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        u = update.effective_user
        if not u:
            return
        existing = state.registry.by_telegram_id(u.id)
        if existing:
            await _send(
                update,
                f"🆔 telegram_id: {u.id}\n"
                f"user_id: {existing.user_id} ({existing.role})\n"
                f"display_name: {existing.display_name}",
            )
        else:
            await _send(
                update,
                f"🆔 telegram_id: {u.id}\n"
                f"username: @{u.username or '-'}\n\n"
                f"관리자에게 이 ID를 전달하면 추가될 수 있습니다.",
            )

    async def users(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not _is_admin(state, update):
            return await _send(update, "🚫 admin 전용 명령입니다.")
        all_users = state.registry.list_users()
        admins = [u for u in all_users if u.role == "admin"]
        members = [u for u in all_users if u.role != "admin"]
        lines = ["👑 admins:"]
        for u in admins:
            lines.append(f"  • {u.user_id} (tg={u.telegram_id})")
        lines.append(f"\n👥 members ({len(members)}):")
        if not members:
            lines.append("  (없음)")
        for m in members:
            tag = " 🧒minor" if m.is_minor else ""
            note = f" — {m.note}" if m.note else ""
            lines.append(
                f"  • {m.user_id} (tg={m.telegram_id}, {m.display_name}){tag}{note}"
            )
        await _send(update, "\n".join(lines))

    def _parse_adduser_args(args: list[str]) -> tuple[str | None, dict]:
        """반환: (target_id, options{alias, minor, note})."""
        opts = {"alias": None, "minor": False, "note": None}
        target = None
        rest: list[str] = []
        i = 0
        while i < len(args):
            tok = args[i]
            low = tok.lower()
            if low == "--minor" or low == "minor":
                opts["minor"] = True
            elif low.startswith("--alias="):
                opts["alias"] = tok.split("=", 1)[1]
            elif low == "--alias" and i + 1 < len(args):
                opts["alias"] = args[i + 1]
                i += 1
            elif target is None and tok.isdigit():
                target = tok
            else:
                rest.append(tok)
            i += 1
        if rest:
            opts["note"] = " ".join(rest)
        return target, opts

    async def adduser(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not _is_admin(state, update):
            return await _send(update, "🚫 admin 전용 명령입니다.")
        # 1) forward 답장 우선
        target_id: str | None = None
        target_name: str | None = None
        msg = update.message
        reply = msg.reply_to_message if msg else None
        if reply and reply.forward_origin is not None:
            origin = reply.forward_origin
            sender = getattr(origin, "sender_user", None)
            if sender:
                target_id = str(sender.id)
                target_name = sender.username
        # 2) 인자 파싱
        arg_target, opts = _parse_adduser_args(list(ctx.args or []))
        if target_id is None:
            target_id = arg_target
        if target_id is None:
            return await _send(
                update,
                "사용법:\n"
                "  /adduser <telegram_id> [--alias name] [--minor] [메모]\n"
                "  또는 메시지 포워드 → 답장으로 /adduser [--alias name] [--minor] [메모]",
            )
        try:
            user = state.registry.add_member(
                telegram_id=target_id,
                alias=opts["alias"],
                display_name=opts["alias"] or target_name or f"tg_{target_id}",
                is_minor=opts["minor"],
                note=opts["note"],
            )
        except UnauthorizedError as e:
            return await _send(update, f"❌ {e}")
        _bus.publish(
            "users.added",
            {
                "user_id": user.user_id,
                "telegram_id": user.telegram_id,
                "is_minor": user.is_minor,
                "by": update.effective_user.id,
                "note": user.note,
            },
        )
        tag = " 🧒minor" if user.is_minor else ""
        await _send(
            update,
            f"✅ 추가됨: {user.user_id} (tg={user.telegram_id}){tag}"
            + (f" — {user.note}" if user.note else ""),
        )

    async def removeuser(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not _is_admin(state, update):
            return await _send(update, "🚫 admin 전용 명령입니다.")
        if not ctx.args:
            return await _send(update, "사용법: /removeuser <user_id 또는 telegram_id>")
        tok = ctx.args[0]
        # 숫자면 telegram_id로 lookup, 아니면 user_id 직접
        target_uid: str | None = None
        if tok.isdigit():
            existing = state.registry.by_telegram_id(tok)
            target_uid = existing.user_id if existing else None
        else:
            target_uid = tok
        if not target_uid:
            return await _send(update, f"❌ 등록되지 않음: {tok}")
        removed = state.registry.remove_member(target_uid)
        if removed:
            _bus.publish("users.removed", {"user_id": target_uid})
            await _send(update, f"🗑 제거됨: {target_uid}")
        else:
            await _send(
                update,
                f"❌ 제거 실패 (admin이거나 등록되지 않음): {target_uid}",
            )

    # ─── 메모리/프로필 조회·편집 ────────────────────────────────
    async def memory_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        uid = _resolve(state, update).user_id
        text = state.memory_store.get_memory(uid)
        await _send(update, text)

    async def profile_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        uid = _resolve(state, update).user_id
        text = state.memory_store.get_user_profile(uid)
        await _send(update, text)

    async def forget_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        if not ctx.args:
            return await _send(
                update,
                "사용법: /forget <키워드>\n"
                "본인 MEMORY.md / USER.md에서 해당 키워드 포함 라인 제거.",
            )
        uid = _resolve(state, update).user_id
        pattern = " ".join(ctx.args).strip()
        removed = state.memory_store.forget(uid, pattern)
        await _send(update, f"🧹 제거된 라인 수: {removed}")

    # ─── 공유 메모리 (admin write, minor blocked) ──────────────────
    async def share_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not _is_admin(state, update):
            return await _send(update, "🚫 admin 전용 명령입니다.")
        fact = " ".join(ctx.args or []).strip()
        if not fact:
            return await _send(
                update,
                "사용법: /share <공유할 사실>\n"
                "예: /share 집 Wi-Fi 비밀번호는 ********",
            )
        uid = _resolve(state, update).user_id
        try:
            cleaned = state.shared_memory.append(uid, fact)
        except UnauthorizedError as e:
            return await _send(update, f"❌ {e}")
        _bus.publish(
            "shared.write",
            {"user_id": uid, "len": len(cleaned)},
        )
        masked = "✏️ PII 마스킹 적용됨" if cleaned != fact else ""
        await _send(update, f"✅ 가족 공유 메모리에 저장됨. {masked}")

    async def shared_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """누구나 자기 가용 범위 내에서 읽기 (미성년자는 빈 응답)."""
        if not await _allowed(state, update):
            return
        uid = _resolve(state, update).user_id
        text = state.shared_memory.read(uid)
        if not text:
            return await _send(update, "(공유 메모리 비어있음 또는 접근 불가)")
        await _send(update, text)

    async def audit_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not _is_admin(state, update):
            return await _send(update, "🚫 admin 전용 명령입니다.")
        entries = state.shared_memory.audit_tail(limit=20)
        if not entries:
            return await _send(update, "감사 로그 비어있음.")
        lines = ["🛡 최근 공유 메모리 감사 로그 (최신 20건):"]
        for e in entries[-20:]:
            ts = e["ts"].split(".")[0].replace("T", " ")
            lines.append(f"{ts} [{e['action']}] {e['user_id']}: {e['content'][:80]}")
        await _send(update, "\n".join(lines))

    # ─── ingest된 문서 접근 ───────────────────────────────────
    def _doc_dirs(user: "User") -> list[tuple[str, Path]]:
        base = Path(get_settings().data_dir) / "documents"
        if user.role == "admin":
            return [("🌐 shared", base / "shared")]
        return [
            ("👤 personal", base / f"user_{user.user_id}"),
            ("🌐 shared", base / "shared"),
        ]

    def _find_doc(user: "User", filename: str) -> tuple[str, Path, bool] | None:
        """반환: (scope_label, path, is_shared)."""
        for label, d in _doc_dirs(user):
            p = d / filename
            if p.exists() and p.is_file():
                return label, p, label.endswith("shared")
        return None

    async def docs_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        user = _resolve(state, update)
        lines = ["📚 ingest된 문서:"]
        total = 0
        for label, d in _doc_dirs(user):
            if not d.exists():
                continue
            files = sorted(p for p in d.iterdir() if p.is_file())
            if not files:
                continue
            lines.append(f"\n{label}:")
            for p in files:
                size_kb = p.stat().st_size / 1024
                lines.append(f"  • {p.name} ({size_kb:.1f} KB)")
                total += 1
        if total == 0:
            lines.append("\n(없음)")
        await _send(update, "\n".join(lines))

    async def doc_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        if not ctx.args:
            return await _send(update, "사용법: /doc <파일명>")
        user = _resolve(state, update)
        filename = " ".join(ctx.args).strip()
        found = _find_doc(user, filename)
        if not found:
            return await _send(update, f"❌ 찾을 수 없음: {filename}")
        from src.memory.text_extractor import (
            UnsupportedFileError,
            extract_text,
        )

        label, path, _ = found
        try:
            text = extract_text(path)
        except UnsupportedFileError as e:
            return await _send(update, f"❌ {e}")
        text = (text or "").strip()
        if not text:
            return await _send(update, "(추출된 텍스트 없음)")
        header = f"📄 {path.name} {label}\n{'─' * 30}\n"
        await _send(update, header + text)

    async def getdoc_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        if not ctx.args:
            return await _send(update, "사용법: /getdoc <파일명>")
        user = _resolve(state, update)
        filename = " ".join(ctx.args).strip()
        found = _find_doc(user, filename)
        if not found:
            return await _send(update, f"❌ 찾을 수 없음: {filename}")
        label, path, _ = found
        try:
            with path.open("rb") as fh:
                await update.effective_chat.send_document(
                    document=fh, filename=path.name, caption=f"{label}"
                )
        except Exception as e:
            await _send(update, f"❌ 전송 실패: {e}")

    async def preview_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        if not ctx.args:
            return await _send(
                update,
                "사용법: /preview <파일명> [페이지수=3] [시작=1]\n"
                "예:\n"
                "  /preview 청약접수증.pdf            첫 3페이지\n"
                "  /preview 청약접수증.pdf 5          첫 5페이지\n"
                "  /preview 청약접수증.pdf 3 4        4페이지부터 3장",
            )
        from src.memory.pdf_render import (
            PdfRenderError,
            page_count,
            render_pdf,
        )

        # 마지막 1~2개 토큰이 숫자면 옵션, 나머지는 파일명
        args = list(ctx.args)
        max_pages = 3
        start = 1
        if args and args[-1].isdigit():
            # 마지막이 숫자면 시작 페이지 (옵션)
            if len(args) >= 2 and args[-2].isdigit():
                start = int(args[-1])
                max_pages = int(args[-2])
                args = args[:-2]
            else:
                max_pages = int(args[-1])
                args = args[:-1]
        filename = " ".join(args).strip()
        if not filename:
            return await _send(update, "❌ 파일명이 비어있습니다.")
        user = _resolve(state, update)
        found = _find_doc(user, filename)
        if not found:
            return await _send(update, f"❌ 찾을 수 없음: {filename}")
        label, path, _ = found
        if path.suffix.lower() != ".pdf":
            return await _send(update, "❌ PDF 파일만 미리보기 가능.")

        max_pages = max(1, min(max_pages, 10))  # 클라이언트 입력 캡
        total = page_count(path)
        try:
            pages = render_pdf(
                path, start=start, max_pages=max_pages
            )
        except PdfRenderError as e:
            return await _send(update, f"❌ 렌더 실패: {e}")
        if not pages:
            return await _send(
                update,
                f"❌ 페이지 없음. 총 {total}페이지, start={start}",
            )

        await update.effective_chat.send_action(ChatAction.UPLOAD_PHOTO)
        # 첫 페이지에 캡션, 그 외는 페이지 번호만
        for i, rp in enumerate(pages):
            caption = (
                f"📄 {path.name} {label}\n"
                f"page {rp.page_number}/{total}"
                if i == 0
                else f"page {rp.page_number}/{total}"
            )
            try:
                await update.effective_chat.send_photo(
                    photo=rp.png_bytes, caption=caption
                )
            except Exception as e:
                _log.warning(f"send_photo failed page={rp.page_number}: {e}")
                await _send(
                    update,
                    f"⚠️ page {rp.page_number} 전송 실패: {e}",
                )
        _bus.publish(
            "doc.preview",
            {
                "user_id": user.user_id,
                "filename": filename,
                "pages": [rp.page_number for rp in pages],
            },
        )

    async def deldoc_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        if not ctx.args:
            return await _send(update, "사용법: /deldoc <파일명>")
        user = _resolve(state, update)
        filename = " ".join(ctx.args).strip()
        is_admin = user.role == "admin"
        # 자신의 권한 범위에만 삭제 허용
        if is_admin:
            target_dir = Path(get_settings().data_dir) / "documents" / "shared"
            scope_label = "🌐 shared"
        else:
            target_dir = (
                Path(get_settings().data_dir) / "documents" / f"user_{user.user_id}"
            )
            scope_label = "👤 personal"
        path = target_dir / filename
        if not path.exists():
            return await _send(
                update,
                f"❌ 본인 권한 범위({scope_label})에 없음: {filename}\n"
                f"  (member는 shared 파일을 삭제할 수 없습니다)",
            )
        # 1) ChromaDB에서 청크 제거
        chunks = state.store.delete_by_filename(
            filename, owner_id=user.user_id, is_admin=is_admin
        )
        # 2) 원본 파일 제거
        try:
            path.unlink()
        except OSError as e:
            return await _send(update, f"⚠️ 파일 제거 실패: {e}")
        _bus.publish(
            "doc.deleted",
            {
                "user_id": user.user_id,
                "filename": filename,
                "scope": scope_label,
                "chunks": chunks,
            },
        )
        await _send(
            update,
            f"🗑 제거됨: {filename} ({scope_label})\n  chunks 제거={chunks}",
        )

    # ─── Skill 조회 (admin/member 모두) ────────────────────────
    async def skills_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _allowed(state, update):
            return
        uid = _resolve(state, update).user_id
        skills = state.skill_manager.list_skills(user_id=uid)
        if not skills:
            return await _send(update, "📚 등록된 skill 없음.")
        lines = [f"📚 사용 가능한 skill ({len(skills)}개):"]
        for s in skills[:30]:
            tag = " 🔞" if s["adult_only"] else ""
            desc = s.get("description", "")[:80]
            lines.append(f"  • {s['name']}{tag} — {desc}")
        await _send(update, "\n".join(lines))

    async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await _send(update, _HELP_GENERAL)

    async def rag_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await _send(update, _HELP_RAG)

    async def ingest_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await _send(update, _HELP_INGEST)

    return {
        "start": start,
        "reset": reset,
        "history": history,
        "status": status,
        "mode": mode,
        "ingest": ingest,
        "message": message,
        "myid": myid,
        "users": users,
        "adduser": adduser,
        "removeuser": removeuser,
        "help": help_cmd,
        "rag_help": rag_help,
        "ingest_help": ingest_help,
        "memory": memory_cmd,
        "profile": profile_cmd,
        "forget": forget_cmd,
        "share": share_cmd,
        "shared": shared_cmd,
        "audit": audit_cmd,
        "skills": skills_cmd,
        "docs": docs_cmd,
        "doc": doc_cmd,
        "getdoc": getdoc_cmd,
        "deldoc": deldoc_cmd,
        "preview": preview_cmd,
    }
