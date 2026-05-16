"""사용자별 MEMORY.md / USER.md 저장소.

격리 보장:
  - 모든 메서드는 user_id를 첫 인자로 받는다. 누락 시 UnauthorizedError.
  - 경로는 _user_dir()에서 검증된 user_id로만 만든다 (path traversal 불가).
  - 쓰기는 tmp 파일 → os.replace로 원자적.
  - 미성년자는 update_user_profile()에서 민감 관찰을 필터링한다.

파일 형식 (Markdown):
  USER.md
    ## 호칭/언어
    ## 선호
    ## 관심사
    ## 컨텍스트
  MEMORY.md
    ## 사실 (Facts)
    ## 진행 중인 과제
    ## 보류/추후
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from threading import RLock

from src.core.logger import get_logger
from src.self_improvement.user_registry import (
    UnauthorizedError,
    UserRegistry,
    get_registry,
)

_log = get_logger("self_improvement.memory")

_MINOR_SENSITIVE_KEYWORDS = (
    "감정", "분노", "우울", "갈등", "가족 갈등", "비밀",
    "이혼", "별거", "재정", "성", "약물", "음주", "흡연",
)


_USER_TEMPLATE = """# 사용자 프로필

## 호칭/언어
한국어로 대화합니다.

## 선호
- (아직 학습되지 않음)

## 관심사
- (아직 학습되지 않음)

## 컨텍스트
- (아직 학습되지 않음)
"""

_MEMORY_TEMPLATE = """# 사용자 메모리

## 사실
- (아직 비어 있음)

## 진행 중인 과제
- (없음)

## 보류/추후
- (없음)
"""


class MemoryStore:
    def __init__(self, data_dir: Path, registry: UserRegistry | None = None) -> None:
        self._data_dir = data_dir
        self._registry = registry or get_registry()
        self._locks: dict[str, RLock] = {}

    # ─── 경로 ──────────────────────────────────────────
    def _user_dir(self, user_id: str) -> Path:
        # registry.get(user_id) → user_id 검증 + 등록 확인 (UnauthorizedError raises)
        self._registry.get(user_id)
        d = self._data_dir / "users" / user_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _lock_for(self, user_id: str) -> RLock:
        if user_id not in self._locks:
            self._locks[user_id] = RLock()
        return self._locks[user_id]

    # ─── 읽기 ──────────────────────────────────────────
    def get_user_profile(self, user_id: str) -> str:
        path = self._user_dir(user_id) / "USER.md"
        if not path.exists():
            self._init_file(path, _USER_TEMPLATE)
        return path.read_text(encoding="utf-8")

    def get_memory(self, user_id: str) -> str:
        path = self._user_dir(user_id) / "MEMORY.md"
        if not path.exists():
            self._init_file(path, _MEMORY_TEMPLATE)
        return path.read_text(encoding="utf-8")

    # ─── 쓰기 (원자적) ──────────────────────────────────
    def append_memory(
        self,
        user_id: str,
        section: str,
        fact: str,
    ) -> None:
        """MEMORY.md의 지정 섹션 끝에 '- {fact}' 한 줄 추가.

        section: '사실', '진행 중인 과제', '보류/추후' 중 하나 권장.
                존재하지 않으면 새 섹션으로 추가.
        """
        if not fact or not fact.strip():
            return
        fact = fact.strip().replace("\n", " ")
        with self._lock_for(user_id):
            path = self._user_dir(user_id) / "MEMORY.md"
            if not path.exists():
                self._init_file(path, _MEMORY_TEMPLATE)
            content = path.read_text(encoding="utf-8")
            new = self._append_to_section(content, section, fact)
            self._atomic_write(path, new)
        _log.info(f"memory append uid={user_id} section={section!r} len={len(fact)}")

    def update_user_profile(
        self,
        user_id: str,
        section: str,
        observation: str,
    ) -> bool:
        """USER.md 지정 섹션에 관찰 1줄 추가.

        미성년자의 경우 민감 키워드가 포함되면 거부하고 False 반환.
        """
        if not observation or not observation.strip():
            return False
        observation = observation.strip().replace("\n", " ")
        user = self._registry.get(user_id)
        if user.is_minor and self._is_sensitive(observation):
            _log.warning(
                f"minor sensitive observation rejected uid={user_id} "
                f"obs={observation[:60]!r}"
            )
            return False
        with self._lock_for(user_id):
            path = self._user_dir(user_id) / "USER.md"
            if not path.exists():
                self._init_file(path, _USER_TEMPLATE)
            content = path.read_text(encoding="utf-8")
            new = self._append_to_section(content, section, observation)
            self._atomic_write(path, new)
        _log.info(
            f"profile update uid={user_id} section={section!r} len={len(observation)}"
        )
        return True

    def forget(self, user_id: str, pattern: str) -> int:
        """MEMORY.md / USER.md에서 pattern을 포함한 라인 제거. 반환: 제거된 라인 수."""
        if not pattern:
            return 0
        removed = 0
        with self._lock_for(user_id):
            d = self._user_dir(user_id)
            for fn in ("MEMORY.md", "USER.md"):
                path = d / fn
                if not path.exists():
                    continue
                lines = path.read_text(encoding="utf-8").splitlines()
                kept = [ln for ln in lines if pattern not in ln]
                cut = len(lines) - len(kept)
                if cut:
                    self._atomic_write(path, "\n".join(kept) + "\n")
                    removed += cut
        _log.info(f"forget uid={user_id} pattern={pattern!r} removed={removed}")
        return removed

    # ─── 내부 ──────────────────────────────────────────
    def _is_sensitive(self, text: str) -> bool:
        lower = text.lower()
        return any(k in text or k in lower for k in _MINOR_SENSITIVE_KEYWORDS)

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".tmp.{int(time.time() * 1000)}")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)

    def _init_file(self, path: Path, template: str) -> None:
        self._atomic_write(path, template)

    def _append_to_section(self, content: str, section: str, line: str) -> str:
        """## section 헤더 다음 본문에 '- line'을 끝에 삽입.
        섹션이 없으면 파일 끝에 새 섹션 추가.
        placeholder ('(아직 비어 있음)', '(없음)', '(아직 학습되지 않음)') 자동 제거.
        """
        target_header = f"## {section}"
        lines = content.splitlines()
        out: list[str] = []
        i = 0
        injected = False
        while i < len(lines):
            out.append(lines[i])
            if not injected and lines[i].strip() == target_header:
                # 섹션 본문 끝(다음 ## 헤더 또는 EOF)까지 스킵하며 placeholder 제거
                j = i + 1
                body: list[str] = []
                while j < len(lines) and not lines[j].startswith("## "):
                    body.append(lines[j])
                    j += 1
                # placeholder 제거
                trimmed_body: list[str] = []
                for b in body:
                    s = b.strip()
                    if s in (
                        "- (아직 비어 있음)",
                        "- (없음)",
                        "- (아직 학습되지 않음)",
                    ):
                        continue
                    trimmed_body.append(b)
                # 본문 끝에 추가
                trimmed_body.append(f"- {line}")
                # 다음 헤더 직전 빈 줄 보장
                if not trimmed_body or trimmed_body[-1].strip() != "":
                    trimmed_body.append("")
                out.extend(trimmed_body)
                i = j
                injected = True
                continue
            i += 1
        if not injected:
            # 새 섹션 추가
            if out and out[-1].strip():
                out.append("")
            out.append(target_header)
            out.append(f"- {line}")
            out.append("")
        result = "\n".join(out)
        if not result.endswith("\n"):
            result += "\n"
        return result
