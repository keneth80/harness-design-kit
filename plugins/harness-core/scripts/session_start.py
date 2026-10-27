#!/usr/bin/env python3
"""session_start: SessionStart.

- init된 프로젝트: 하네스 상태 한 줄 + docs/codemap.md(크면 디렉터리 목록만)를 컨텍스트에 넣는다.
- init 안 된 프로젝트:
    ~/.claude/harness.config.json에 "auto_init": true면 조건(깃 저장소 + 소스 파일 수)을 보고
    harness.config.json을 자동으로 만든다. 아니면 규모가 큰 프로젝트에서만 init을 한 줄 권한다.
  보안 게이트(bash_gate, file_gate)는 init과 무관하게 모든 프로젝트에서 이미 동작 중이다.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

HOOK = "session_start"
SRC_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".go", ".rs",
           ".java", ".kt", ".swift", ".rb", ".php", ".cs", ".dart"}
SKIP = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next",
        "coverage", ".claude", "target", "out", ".turbo", ".cache", "vendor", "Pods"}
MAX_INLINE = 6000


def count_sources(root, limit=400, budget=0.8):
    """소스 파일 수를 limit까지만 센다 (큰 저장소에서 느려지지 않게 시간 예산도 둔다)."""
    n, start = 0, time.time()
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP and not d.startswith(".")]
        n += sum(1 for f in fns if os.path.splitext(f)[1] in SRC_EXT)
        if n >= limit or time.time() - start > budget:
            break
    return n


def newest_source_mtime(root, budget=0.8):
    newest, start = 0.0, time.time()
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP and d != "docs" and not d.startswith(".")]
        for f in fns:
            if os.path.splitext(f)[1] in SRC_EXT:
                try:
                    newest = max(newest, os.path.getmtime(os.path.join(dp, f)))
                except OSError:
                    pass
        if time.time() - start > budget:
            break
    return newest


def codemap_block(proj):
    path = os.path.join(proj, "docs", "codemap.md")
    if not os.path.exists(path):
        return "코드맵이 아직 없습니다. 작업이 끝나면 자동 생성되며, 지금 만들려면 /harness-core:codemap 을 실행하세요."
    with open(path, encoding="utf-8") as f:
        content = f.read()
    stale = ""
    try:
        if newest_source_mtime(proj) > os.path.getmtime(path):
            stale = "\n(코드가 코드맵 생성 이후 바뀌었습니다. 작업 종료 시 자동 갱신됩니다.)"
    except OSError:
        pass
    if len(content) <= MAX_INLINE:
        return "=== 프로젝트 코드맵 (docs/codemap.md) ===\n" + content + stale
    dirs = [line for line in content.splitlines() if line.startswith("## ")]
    return ("=== 프로젝트 코드맵 (요약: 디렉터리 목록) ===\n" + "\n".join(dirs)
            + "\n전체는 docs/codemap.md를 읽으세요." + stale)


def write_minimal_config(proj):
    cfg = {
        "version": 2,
        "drift_guard": {"mode": "block", "warn_paths": []},
        "verify": {},
    }
    with open(os.path.join(proj, _lib.CONFIG_FILE), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    event = _lib.read_event()
    proj = _lib.project_dir(event)
    user_cfg = _lib._read_json(_lib.USER_CONFIG) or {}

    if not _lib.is_initialized(proj):
        if not os.path.isdir(os.path.join(proj, ".git")):
            sys.exit(0)
        n = count_sources(proj)
        min_files = int(user_cfg.get("auto_init_min_files", 30))
        if user_cfg.get("auto_init") and n >= min_files:
            try:
                write_minimal_config(proj)
                _lib.audit(proj, HOOK, "warn", proj, "auto_init")
                _lib.add_context(
                    "[harness] 이 프로젝트에 harness.config.json을 자동 생성했습니다 (auto_init). "
                    "편집 후 검증과 코드맵이 켜졌습니다. 도메인 설계 사이클은 /harness-core:init 에서 안내합니다.",
                    "SessionStart",
                    user_message="harness: auto_init으로 harness.config.json을 만들었습니다.")
            except OSError:
                pass
            sys.exit(0)
        if n >= min_files:
            _lib.add_context(
                "[harness] 보안 게이트는 켜져 있지만 이 프로젝트는 하네스 워크플로우(편집 후 검증, 코드맵, "
                "드리프트 가드)가 꺼져 있습니다. 사용자가 원하면 /harness-core:init 으로 켤 수 있다고 "
                "한 번만 알려주세요. 사용자가 다른 일을 하고 있으면 굳이 언급하지 마세요.",
                "SessionStart")
        sys.exit(0)

    cfg = _lib.load_config(proj)
    dg = (cfg.get("drift_guard") or {}).get("mode", "block")
    has_domains = os.path.isdir(os.path.join(proj, "docs", "domains"))
    lines = [f"[harness] 이 프로젝트는 하네스가 켜져 있습니다. drift_guard={dg}"
             + (", 도메인 설계 사이클 사용 중 (docs/domains/)" if has_domains else "")
             + ". 보안 게이트가 시크릿 읽기·외부 전송·검증기 수정을 막습니다. 막히면 우회하지 말고 사용자에게 알리세요."]
    if (cfg.get("codemap") or {}).get("enabled", True):
        lines.append(codemap_block(proj))
    _lib.audit(proj, HOOK, "pass", proj)
    _lib.add_context("\n\n".join(lines), "SessionStart")
    sys.exit(0)


if __name__ == "__main__":
    main()
