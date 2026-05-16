"""가족 공유 메모리.

쓰기 권한: admin (registry.is_admin)
읽기 권한: admin + 일반 user. 미성년자는 빈 문자열 반환.
모든 시도(성공·거부)는 _shared_audit.log에 기록.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from src.core.logger import get_logger
from src.self_improvement import pii_filter
from src.self_improvement.user_registry import (
    UnauthorizedError,
    UserRegistry,
    get_registry,
)

_log = get_logger("self_improvement.shared")


_TEMPLATE = """# 가족 공유 메모리

이 파일의 내용은 admin이 명시적으로 공유한 사실만 포함합니다.
미성년 사용자에게는 노출되지 않습니다.

## 공유 사실
- (아직 비어 있음)
"""


class SharedMemoryStore:
    def __init__(self, data_dir: Path, registry: UserRegistry | None = None) -> None:
        self._dir = data_dir / "shared"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "SHARED_MEMORY.md"
        self._audit_path = self._dir / "_shared_audit.log"
        self._registry = registry or get_registry()
        self._lock = RLock()

    # ─── 읽기 ─────────────────────────────────────────
    def read(self, user_id: str) -> str:
        user = self._registry.get(user_id)
        if user.is_minor:
            return ""
        if not self._path.exists():
            return ""
        return self._path.read_text(encoding="utf-8")

    # ─── 쓰기 (admin only) ────────────────────────────
    def append(
        self,
        user_id: str,
        fact: str,
        *,
        section: str = "공유 사실",
    ) -> str:
        """admin만 쓰기 가능. PII 마스킹 후 저장. 시도는 모두 감사로그."""
        user = self._registry.get(user_id)
        fact = (fact or "").strip()
        if not fact:
            raise ValueError("빈 fact")
        if user.role != "admin":
            self._audit(user_id, "DENIED_WRITE", fact)
            raise UnauthorizedError(
                f"공유 메모리 쓰기는 admin만 가능 — user_id={user_id}"
            )
        cleaned = pii_filter.clean(fact, level="shared")
        with self._lock:
            if not self._path.exists():
                self._atomic_write(_TEMPLATE)
            content = self._path.read_text(encoding="utf-8")
            new = self._append_to_section(content, section, cleaned)
            self._atomic_write(new)
        self._audit(user_id, "WRITE", cleaned)
        _log.info(f"shared append by={user_id} len={len(cleaned)}")
        return cleaned

    def forget(self, user_id: str, pattern: str) -> int:
        """admin만 제거 가능."""
        user = self._registry.get(user_id)
        if user.role != "admin":
            self._audit(user_id, "DENIED_FORGET", pattern)
            raise UnauthorizedError(
                f"공유 메모리 삭제는 admin만 가능 — user_id={user_id}"
            )
        with self._lock:
            if not self._path.exists():
                return 0
            lines = self._path.read_text(encoding="utf-8").splitlines()
            kept = [ln for ln in lines if pattern not in ln]
            removed = len(lines) - len(kept)
            if removed:
                self._atomic_write("\n".join(kept) + "\n")
        self._audit(user_id, "FORGET", f"pattern={pattern} removed={removed}")
        return removed

    # ─── 감사 ─────────────────────────────────────────
    def _audit(self, user_id: str, action: str, content: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        snippet = (content or "").replace("\t", " ").replace("\n", " ")[:200]
        line = f"{ts}\t{user_id}\t{action}\t{snippet}\n"
        try:
            with self._audit_path.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError as e:
            _log.error(f"audit log write failed: {e}")

    def audit_tail(self, limit: int = 50) -> list[dict]:
        if not self._audit_path.exists():
            return []
        lines = self._audit_path.read_text(encoding="utf-8").splitlines()
        out = []
        for ln in lines[-limit:]:
            parts = ln.split("\t", 3)
            if len(parts) != 4:
                continue
            out.append(
                {
                    "ts": parts[0],
                    "user_id": parts[1],
                    "action": parts[2],
                    "content": parts[3],
                }
            )
        return out

    # ─── 내부 ──────────────────────────────────────────
    def _atomic_write(self, content: str) -> None:
        tmp = self._path.with_suffix(
            self._path.suffix + f".tmp.{int(time.time() * 1000)}"
        )
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, self._path)

    def _append_to_section(self, content: str, section: str, line: str) -> str:
        target = f"## {section}"
        lines = content.splitlines()
        out: list[str] = []
        i = 0
        injected = False
        while i < len(lines):
            out.append(lines[i])
            if not injected and lines[i].strip() == target:
                j = i + 1
                body: list[str] = []
                while j < len(lines) and not lines[j].startswith("## "):
                    body.append(lines[j])
                    j += 1
                # placeholder 제거
                trimmed = [
                    b for b in body if b.strip() != "- (아직 비어 있음)"
                ]
                trimmed.append(f"- {line}")
                if not trimmed or trimmed[-1].strip() != "":
                    trimmed.append("")
                out.extend(trimmed)
                i = j
                injected = True
                continue
            i += 1
        if not injected:
            if out and out[-1].strip():
                out.append("")
            out.append(target)
            out.append(f"- {line}")
            out.append("")
        result = "\n".join(out)
        if not result.endswith("\n"):
            result += "\n"
        return result
