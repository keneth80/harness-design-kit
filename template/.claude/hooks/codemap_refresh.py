#!/usr/bin/env python3
"""
codemap_refresh: Stop 훅.
에이전트가 한 작업(응답)을 마칠 때 docs/codemap.md를 다시 생성한다.
매 편집마다(PostToolUse) 돌리면 느리므로, 작업 종료 시 한 번만 갱신해
다음 세션이 항상 최신 코드맵으로 시작하게 한다.

- codemap.py를 같은 디렉터리에서 호출.
- 소스가 코드맵보다 최신일 때만 갱신(불필요한 재생성 방지).
- 조용히 동작(성공 시 출력 최소화). 실패해도 작업을 막지 않는다.
"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from monitor import log_event
except Exception:
    def log_event(*a, **k): pass

def read_event():
    try: return json.loads(sys.stdin.read())
    except Exception: return {}

def newest_source_mtime(root):
    newest = 0
    skip = {"node_modules",".git","__pycache__",".venv","venv","dist","build",".next",".claude","docs"}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in skip]
        for fn in fns:
            if os.path.splitext(fn)[1] in {".py",".js",".jsx",".ts",".tsx"}:
                try: newest = max(newest, os.path.getmtime(os.path.join(dp, fn)))
                except OSError: pass
    return newest

def main():
    ev = read_event()
    cwd = ev.get("cwd") or os.getcwd()
    codemap_md = os.path.join(cwd, "docs", "codemap.md")
    script = os.path.join(cwd, ".claude", "hooks", "codemap.py")

    if not os.path.exists(script):
        sys.exit(0)  # 코드맵 스크립트가 없으면 조용히 종료

    # 소스가 코드맵보다 최신일 때만 갱신
    try:
        if os.path.exists(codemap_md) and newest_source_mtime(cwd) <= os.path.getmtime(codemap_md):
            sys.exit(0)  # 이미 최신
    except OSError:
        pass

    try:
        r = subprocess.run([sys.executable, script, cwd],
                          capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            log_event(cwd, "codemap_refresh", "docs/codemap.md", "refreshed")
            print("[codemap] 코드맵을 갱신했습니다 (docs/codemap.md).")
    except Exception:
        pass  # 갱신 실패해도 작업 흐름은 막지 않음
    sys.exit(0)

if __name__ == "__main__":
    main()
