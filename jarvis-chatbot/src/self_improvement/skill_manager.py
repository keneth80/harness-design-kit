"""전역 Skill 저장소.

- 누가 만들든 모두 사용 가능 (skill = 전역 공유 자산)
- 추출 시 PII/credential 자동 마스킹 (skill 레벨 — 가장 엄격)
- frontmatter에 created_by 기록 (감사용, 사용자에게 노출 안 함)
- adult_only: true skill은 미성년자 검색에서 제외
- 검색: 단순 키워드 매칭 (Phase 5는 v1, 향후 임베딩 가능)
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from src.core.logger import get_logger
from src.self_improvement import pii_filter
from src.self_improvement.user_registry import (
    UserRegistry,
    get_registry,
)

_log = get_logger("self_improvement.skill")


# Skill 추출 시 LLM 시스템 프롬프트
_EXTRACT_SYSTEM = (
    "당신은 대화에서 재사용 가능한 절차(skill)를 추출하는 분석가입니다. "
    "PII(이메일·전화·API 키·이름)는 모두 <REDACTED> 또는 <NAME>으로 마스킹하세요. "
    "결과는 JSON 한 덩어리로만 출력합니다.\n"
    "스키마: {\n"
    '  "name": "snake_case_식별자",\n'
    '  "description": "한 줄 설명",\n'
    '  "steps": ["1. ...", "2. ..."],\n'
    '  "adult_only": false,\n'
    '  "tags": ["...", "..."]\n'
    "}\n"
    "skill이 없거나 추출 가치 없으면 {\"name\": \"\"} 만 출력."
)


_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def _slugify(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = s.strip("_")
    return s[:64]


def _front_matter(meta: dict) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def _parse_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text
    meta: dict[str, str | list[str]] = {}
    for ln in parts[0][4:].splitlines():
        if ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        k = k.strip()
        v = v.strip()
        if k in ("tags",):
            meta[k] = [t.strip() for t in v.split(",") if t.strip()]
        elif v.lower() in ("true", "false"):
            meta[k] = v.lower() == "true"
        else:
            meta[k] = v
    return meta, parts[1].lstrip()


class SkillManager:
    def __init__(
        self,
        data_dir: Path,
        client=None,
        *,
        registry: UserRegistry | None = None,
    ) -> None:
        self._dir = data_dir / "skills"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._registry = registry or get_registry()
        self._client = client  # LMStudioClient. None이면 extract 비활성.
        self._lock = RLock()
        self._audit_path = self._dir / "_skills_audit.log"

    # ─── 검색/조회 ────────────────────────────────────
    def list_skills(self, user_id: str | None = None) -> list[dict]:
        """user_id 주면 미성년자 필터 적용."""
        skills: list[dict] = []
        for p in sorted(self._dir.glob("*.md")):
            if p.name.startswith("_"):
                continue
            try:
                content = p.read_text(encoding="utf-8")
            except OSError:
                continue
            meta, body = _parse_front_matter(content)
            skills.append(
                {
                    "name": p.stem,
                    "description": str(meta.get("description", "")),
                    "tags": meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
                    "adult_only": bool(meta.get("adult_only", False)),
                    "body": body,
                }
            )
        if user_id is None:
            return skills
        user = self._registry.get(user_id)
        if user.is_minor:
            return [s for s in skills if not s["adult_only"]]
        return skills

    def find_relevant(self, user_id: str, query: str, top_k: int = 3) -> list[dict]:
        candidates = self.list_skills(user_id=user_id)
        if not query.strip():
            return []
        q_tokens = {t.lower() for t in query.split() if len(t) > 1}
        scored = []
        for s in candidates:
            hay = (
                s["name"]
                + " "
                + s["description"]
                + " "
                + " ".join(s.get("tags") or [])
                + " "
                + s["body"]
            ).lower()
            score = sum(1 for t in q_tokens if t in hay)
            if score > 0:
                scored.append((score, s))
        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[:top_k]]

    def get(self, name: str) -> dict | None:
        p = self._dir / f"{name}.md"
        if not p.exists():
            return None
        meta, body = _parse_front_matter(p.read_text(encoding="utf-8"))
        return {
            "name": name,
            "description": str(meta.get("description", "")),
            "tags": meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
            "adult_only": bool(meta.get("adult_only", False)),
            "created_by": str(meta.get("created_by", "")),
            "body": body,
        }

    # ─── 추출 ────────────────────────────────────────
    async def maybe_extract(
        self,
        user_id: str,
        conversation: list[dict],
        *,
        hint: str | None = None,
    ) -> str | None:
        """LLM에게 skill 추출 요청. 성공 시 skill 이름 반환."""
        if self._client is None:
            return None
        user = self._registry.get(user_id)
        msgs = [
            {"role": "system", "content": _EXTRACT_SYSTEM},
            {
                "role": "user",
                "content": self._build_user_prompt(conversation, hint),
            },
        ]
        try:
            raw = await self._client.chat(
                msgs, temperature=0.2, max_tokens=800
            )
        except Exception as e:
            _log.warning(f"skill LLM error uid={user_id}: {e}")
            return None

        skill = self._parse_skill(raw)
        if not skill or not skill.get("name"):
            return None

        # 결정론적 PII 필터 추가 적용 (이중 안전)
        skill["description"] = pii_filter.clean(
            skill.get("description", ""), level="skill"
        )
        steps = [pii_filter.clean(s, level="skill") for s in skill.get("steps", [])]
        skill["steps"] = steps

        name = self._save(skill, created_by=user_id)
        self._audit(user_id, "CREATE", name)
        return name

    def _build_user_prompt(self, conversation: list[dict], hint: str | None) -> str:
        lines = []
        if hint:
            lines.append(f"힌트: {hint}")
        lines.append("=== 대화 ===")
        for m in conversation:
            role = m.get("role")
            if role not in ("user", "assistant"):
                continue
            content = (m.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"[{role}] {content}")
        return "\n".join(lines)

    @staticmethod
    def _parse_skill(raw: str) -> dict | None:
        if not raw:
            return None
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        return obj

    def _save(self, skill: dict, *, created_by: str) -> str:
        name = _slugify(skill.get("name", ""))
        if not _NAME_RE.match(name):
            return ""
        meta = {
            "name": name,
            "description": skill.get("description", ""),
            "tags": skill.get("tags", []),
            "adult_only": bool(skill.get("adult_only", False)),
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        steps = skill.get("steps") or []
        body_lines = [
            f"# {name}",
            "",
            skill.get("description", ""),
            "",
            "## 절차",
        ]
        for s in steps:
            body_lines.append(f"- {s}")
        body = "\n".join(body_lines) + "\n"
        content = _front_matter(meta) + "\n\n" + body
        # PII 한 번 더 통과 (전체 본문)
        content = pii_filter.clean(content, level="skill")
        path = self._dir / f"{name}.md"
        with self._lock:
            tmp = path.with_suffix(path.suffix + f".tmp.{int(time.time() * 1000)}")
            tmp.write_text(content, encoding="utf-8")
            os.replace(tmp, path)
        _log.info(f"skill saved name={name} by={created_by}")
        return name

    # ─── 감사 ─────────────────────────────────────────
    def _audit(self, user_id: str, action: str, content: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        line = f"{ts}\t{user_id}\t{action}\t{content[:200]}\n"
        try:
            with self._audit_path.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError as e:
            _log.error(f"skill audit failed: {e}")

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
                {"ts": parts[0], "user_id": parts[1], "action": parts[2], "content": parts[3]}
            )
        return out
