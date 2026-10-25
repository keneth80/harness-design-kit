#!/usr/bin/env python3
"""codemap_refresh: Stop.

init된 프로젝트에서 소스가 docs/codemap.md보다 새로우면 코드맵을 다시 만든다.
매 편집마다 돌리면 느려서 응답이 끝날 때 한 번만 돈다. 실패해도 아무것도 막지 않는다.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402
from session_start import newest_source_mtime  # noqa: E402

HOOK = "codemap_refresh"


def main():
    event = _lib.read_event()
    proj = _lib.project_dir(event)
    if not _lib.is_initialized(proj):
        sys.exit(0)
    if not (_lib.load_config(proj).get("codemap") or {}).get("enabled", True):
        sys.exit(0)
    out = os.path.join(proj, "docs", "codemap.md")
    try:
        if os.path.exists(out) and newest_source_mtime(proj, budget=2.0) <= os.path.getmtime(out):
            sys.exit(0)
    except OSError:
        pass
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codemap.py")
    try:
        r = subprocess.run([sys.executable, script, proj], capture_output=True, text=True, timeout=60)
        _lib.audit(proj, HOOK, "pass" if r.returncode == 0 else "error", out, (r.stderr or "")[:200])
    except Exception as exc:
        _lib.audit(proj, HOOK, "error", out, repr(exc))
    sys.exit(0)


if __name__ == "__main__":
    main()
