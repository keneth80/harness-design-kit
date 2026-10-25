#!/usr/bin/env python3
"""design_only_gate: PreToolUse(Write|Edit|MultiEdit|NotebookEdit|Bash) — harness-codex.

이 플러그인이 켜진 프로젝트에서 Claude는 설계만 한다. 코드는 Codex CLI가 쓴다.
설계 산출물 경로 밖의 파일 쓰기를 막는다.

허용 경로 (harness.config.json의 "codex": {"design_paths": [...]}로 바꿀 수 있음)
  docs/**, *.md, **/AGENTS.md, **/AGENTS.override.md, CONTEXT.md, harness.config.json,
  .claude/**, .codex/**

Bash는 리다이렉션(>, >>)·tee·cp·mv의 대상만 본다 (최선 노력 수준. 주 방어선은 Write/Edit 차단).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

HOOK = "design_only_gate"
DEFAULT_DESIGN_PATHS = ["docs/**", "*.md", "**/*.md", "AGENTS.md", "**/AGENTS.override.md",
                        "harness.config.json", ".claude/**", ".codex/**"]
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def allowed(rel, patterns):
    return _lib.glob_match(rel, patterns)


def bash_targets(cmd):
    targets = re.findall(r"(?:^|[\s;&|])(?:\d?>>?|&>>?)\s*([^\s;&|<>]+)", cmd)
    for m in re.finditer(r"\btee\s+((?:-\w+\s+)*)([^\s;&|<>]+)", cmd):
        targets.append(m.group(2))
    for m in re.finditer(r"\b(?:cp|mv|install)\s+(?:-\w+\s+)*\S+\s+([^\s;&|<>]+)", cmd):
        targets.append(m.group(1))
    return [t.strip("'\"") for t in targets if t not in ("/dev/null", "&1", "&2")]


def main():
    event = _lib.read_event()
    tool = event.get("tool_name", "")
    proj = _lib.project_dir(event)
    cfg = _lib.load_config(proj)
    patterns = (cfg.get("codex") or {}).get("design_paths") or DEFAULT_DESIGN_PATHS

    if tool in WRITE_TOOLS:
        targets = [_lib.tool_target(event)]
    elif tool == "Bash":
        targets = bash_targets((event.get("tool_input") or {}).get("command") or "")
    else:
        sys.exit(0)

    blocked = []
    for t in targets:
        if not t:
            continue
        full = _lib.abspath_in(proj, t)
        rel = _lib.relpath_or_none(full, proj)
        if rel is None:
            continue  # 프로젝트 밖(/tmp 등)은 이 게이트의 관심사가 아니다
        if not allowed(rel.replace("\\", "/"), patterns):
            blocked.append(rel)

    if blocked:
        reason = ("[design_only] 이 프로젝트는 설계 전용 모드(harness-codex)입니다. Claude는 코드를 쓰지 않습니다: "
                  + ", ".join(blocked[:5])
                  + ". 필요한 규칙을 도메인 매뉴얼에 반영하고 /harness-codex:codex-handoff로 AGENTS.override.md를 "
                    "내보낸 뒤 Codex CLI에 구현을 맡기세요. 설계 산출물 경로를 바꾸려면 harness.config.json의 "
                    "codex.design_paths를 수정합니다.")
        _lib.audit(proj, HOOK, "deny", ", ".join(blocked), reason)
        _lib.decide("deny", reason)
    sys.exit(0)


if __name__ == "__main__":
    main()
