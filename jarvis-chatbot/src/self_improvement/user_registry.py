"""사용자 레지스트리.

ID 스키마 (하이브리드):
  - 명시적 별칭(예: 'kenneth')이 있으면 그것이 canonical user_id
  - 별칭이 없는 텔레그램 사용자는 'tg_<telegram_id>'로 자동 변환
  - registry.json은 (canonical user_id) → User 메타데이터 매핑

권한:
  - admin: .env TELEGRAM_CHAT_ID에 해당 telegram_id가 있는 사람만
  - member: registry.json에 등록되어 있고 admin이 아닌 사람
  - 그 외: UnauthorizedError

보안:
  - get(), by_telegram_id()는 모두 검증 포함
  - path traversal('/', '..', '\\') 차단
  - user_id는 ^[a-zA-Z][a-zA-Z0-9_-]{0,63}$ 패턴만 허용
  - registry.json 쓰기는 원자적 (os.replace)
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from src.core.config import get_settings
from src.core.logger import get_logger

_log = get_logger("self_improvement.registry")

_USER_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{0,63}$")


class UnauthorizedError(Exception):
    """사용자 인증/권한 실패. 결코 기본 허용 동작과 함께 사용하지 말 것."""


@dataclass(frozen=True)
class User:
    user_id: str
    display_name: str
    role: Literal["admin", "user"] = "user"
    language: str = "ko"
    is_minor: bool = False
    telegram_id: str | None = None
    agents: tuple[str, ...] = field(default_factory=tuple)
    note: str | None = None


def _validate_user_id(user_id: str | None) -> str:
    if not user_id or not isinstance(user_id, str):
        raise UnauthorizedError("user_id가 비어있거나 잘못된 타입")
    if any(c in user_id for c in ("/", "\\", "..")):
        raise UnauthorizedError(f"user_id에 경로 문자 포함: {user_id!r}")
    if not _USER_ID_RE.match(user_id):
        raise UnauthorizedError(f"user_id 패턴 불일치: {user_id!r}")
    return user_id


def _tg_to_user_id(tg_id: str | int) -> str:
    """텔레그램 ID → 자동 별칭 'tg_<digits>'."""
    s = str(tg_id).strip()
    if not s.isdigit():
        raise UnauthorizedError(f"telegram_id는 숫자여야 함: {tg_id!r}")
    return f"tg_{s}"


class UserRegistry:
    def __init__(self, registry_path: Path) -> None:
        self._path = registry_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._users: dict[str, User] = {}
        self._tg_index: dict[str, str] = {}  # telegram_id → user_id
        self._load()
        # admin은 .env에서 자동 동기화
        self._sync_admins_from_env()

    # ─── 로딩/저장 ──────────────────────────────────────
    def _load(self) -> None:
        if not self._path.exists():
            self._users = {}
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as e:
            raise UnauthorizedError(f"registry.json 손상: {e}")
        users: dict[str, User] = {}
        tg_idx: dict[str, str] = {}
        for uid, data in raw.items():
            try:
                _validate_user_id(uid)
            except UnauthorizedError:
                _log.warning(f"skip invalid uid in registry: {uid!r}")
                continue
            agents = tuple(data.get("agents") or ())
            user = User(
                user_id=uid,
                display_name=str(data.get("display_name", uid)),
                role=data.get("role", "user"),
                language=data.get("language", "ko"),
                is_minor=bool(data.get("is_minor", False)),
                telegram_id=(
                    str(data["telegram_id"]) if data.get("telegram_id") else None
                ),
                agents=agents,
                note=data.get("note"),
            )
            users[uid] = user
            if user.telegram_id:
                tg_idx[user.telegram_id] = uid
        self._users = users
        self._tg_index = tg_idx
        _log.info(f"registry loaded: users={len(users)} from {self._path}")

    def _atomic_write(self) -> None:
        with self._lock:
            data = {
                uid: {
                    "display_name": u.display_name,
                    "role": u.role,
                    "language": u.language,
                    "is_minor": u.is_minor,
                    "telegram_id": u.telegram_id,
                    "agents": list(u.agents),
                    "note": u.note,
                }
                for uid, u in self._users.items()
            }
            tmp = self._path.with_suffix(f".tmp.{int(time.time()*1000)}")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(tmp, self._path)
            _log.info(f"registry saved: users={len(data)}")

    def _sync_admins_from_env(self) -> None:
        """env의 TELEGRAM_CHAT_ID 각 id가 registry에 없으면 admin 엔트리 자동 생성.
        이미 있으면 role을 admin으로 보정."""
        settings = get_settings()
        env_admins = [str(x) for x in settings.allowed_user_ids]
        if not env_admins:
            return
        dirty = False
        for tg_id in env_admins:
            existing_uid = self._tg_index.get(tg_id)
            if existing_uid:
                u = self._users[existing_uid]
                if u.role != "admin":
                    self._users[existing_uid] = User(**{**asdict(u), "role": "admin"})
                    dirty = True
            else:
                uid = _tg_to_user_id(tg_id)
                self._users[uid] = User(
                    user_id=uid,
                    display_name="Admin",
                    role="admin",
                    telegram_id=tg_id,
                )
                self._tg_index[tg_id] = uid
                dirty = True
                _log.info(f"admin auto-registered uid={uid} tg={tg_id}")
        if dirty:
            self._atomic_write()

    # ─── 조회 ──────────────────────────────────────────
    def get(self, user_id: str) -> User:
        uid = _validate_user_id(user_id)
        if uid not in self._users:
            raise UnauthorizedError(f"등록되지 않은 user_id: {uid!r}")
        return self._users[uid]

    def by_telegram_id(self, tg_id: str | int) -> User | None:
        s = str(tg_id).strip()
        if not s.isdigit():
            return None
        # 1) 명시적 등록 우선
        uid = self._tg_index.get(s)
        if uid:
            return self._users[uid]
        # 2) admin은 .env로도 식별 (registry sync가 처리하지만 race-safe)
        settings = get_settings()
        if s in (str(x) for x in settings.allowed_user_ids):
            return User(
                user_id=_tg_to_user_id(s),
                display_name="Admin",
                role="admin",
                telegram_id=s,
            )
        return None

    def is_admin(self, user_id: str) -> bool:
        return self.get(user_id).role == "admin"

    def list_users(self) -> list[User]:
        return list(self._users.values())

    # ─── 변경 ──────────────────────────────────────────
    def add_member(
        self,
        *,
        telegram_id: str | int,
        alias: str | None = None,
        display_name: str | None = None,
        is_minor: bool = False,
        language: str = "ko",
        note: str | None = None,
    ) -> User:
        tg = str(telegram_id).strip()
        if not tg.isdigit():
            raise UnauthorizedError(f"telegram_id 비숫자: {telegram_id!r}")
        with self._lock:
            if tg in self._tg_index:
                existing = self._users[self._tg_index[tg]]
                raise UnauthorizedError(
                    f"이미 등록된 telegram_id: {tg} (user_id={existing.user_id})"
                )
            uid = _validate_user_id(alias) if alias else _tg_to_user_id(tg)
            if uid in self._users:
                raise UnauthorizedError(f"이미 존재하는 user_id: {uid}")
            # admin 별도 등록 금지 (admin은 env로만 관리)
            settings = get_settings()
            if tg in (str(x) for x in settings.allowed_user_ids):
                raise UnauthorizedError(
                    f"telegram_id {tg}는 admin입니다. /adduser로 member 등록 불가."
                )
            user = User(
                user_id=uid,
                display_name=display_name or uid,
                role="user",
                language=language,
                is_minor=is_minor,
                telegram_id=tg,
                note=note,
            )
            self._users[uid] = user
            self._tg_index[tg] = uid
            self._atomic_write()
            _log.info(f"member added uid={uid} tg={tg} minor={is_minor}")
            return user

    def remove_member(self, user_id: str) -> bool:
        uid = _validate_user_id(user_id)
        with self._lock:
            user = self._users.get(uid)
            if not user or user.role == "admin":
                return False
            self._users.pop(uid)
            if user.telegram_id:
                self._tg_index.pop(user.telegram_id, None)
            self._atomic_write()
            _log.info(f"member removed uid={uid}")
            return True

    def set_alias(self, user_id: str, new_alias: str) -> User:
        """기존 user_id를 명시 별칭으로 rename. admin도 가능."""
        old = _validate_user_id(user_id)
        new = _validate_user_id(new_alias)
        with self._lock:
            if old not in self._users:
                raise UnauthorizedError(f"존재하지 않는 uid: {old}")
            if new in self._users:
                raise UnauthorizedError(f"이미 존재하는 uid: {new}")
            user = self._users.pop(old)
            renamed = User(**{**asdict(user), "user_id": new})
            self._users[new] = renamed
            if renamed.telegram_id:
                self._tg_index[renamed.telegram_id] = new
            self._atomic_write()
            _log.info(f"alias renamed {old} → {new}")
            return renamed


# ─── 싱글톤 헬퍼 ──────────────────────────────────────
_singleton: UserRegistry | None = None


def get_registry() -> UserRegistry:
    global _singleton
    if _singleton is None:
        settings = get_settings()
        _singleton = UserRegistry(settings.data_dir / "users" / "_registry.json")
    return _singleton


def reset_registry_for_tests() -> None:
    """테스트용. 프로덕션에서 호출 금지."""
    global _singleton
    _singleton = None
