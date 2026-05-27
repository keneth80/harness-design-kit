#!/usr/bin/env python3
"""
codemap_session: SessionStart 훅.
세션이 시작될 때 docs/codemap.md를 에이전트 컨텍스트에 주입한다.
세션이 끊겼다 재개되어도 에이전트가 전체 코드를 다 읽지 않고 구조를 파악하게 한다.

동작:
  - docs/codemap.md가 있으면 그 내용을 stdout으로 출력(에이전트 컨텍스트로 들어감).
  - 코드맵이 오래됐으면(소스가 codemap.md보다 최신) 갱신을 권하는 안내를 덧붙인다.
  - 없으면 생성 방법만 짧게 안내.

SessionStart 훅의 stdout은 세션 컨텍스트에 추가된다.
너무 길면 컨텍스트를 잡아먹으므로, 코드맵이 매우 크면 요약 안내만 하고 전체는 참조하게 한다.
"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from monitor import log_event
except Exception:
    def log_event(*a, **k): pass

MAX_INLINE_CHARS = 6000  # 이보다 크면 전체를 넣지 않고 경로만 안내


def read_event():
    try:
        return json.loads(sys.stdin.read())
    except Exception:
        return {}


def newest_source_mtime(root):
    newest = 0
    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".claude", "docs"}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in skip]
        for fn in fns:
            if os.path.splitext(fn)[1] in {".py", ".js", ".jsx", ".ts", ".tsx"}:
                try:
                    m = os.path.getmtime(os.path.join(dp, fn))
                    newest = max(newest, m)
                except OSError:
                    pass
    return newest


def main():
    ev = read_event()
    cwd = ev.get("cwd") or os.getcwd()
    codemap = os.path.join(cwd, "docs", "codemap.md")

    if not os.path.exists(codemap):
        # 소스가 있는 프로젝트면 생성 권유, 아니면 조용히 종료
        print("[codemap] docs/codemap.md가 없습니다. 코드 구조 지도를 만들려면 "
              "`python3 .claude/hooks/codemap.py` 를 실행하세요.")
        sys.exit(0)

    content = open(codemap, encoding="utf-8").read()

    # 신선도 점검: 소스가 코드맵보다 최신이면 경고
    stale = ""
    try:
        if newest_source_mtime(cwd) > os.path.getmtime(codemap):
            stale = ("\n⚠️ 코드가 코드맵 생성 이후 변경됨. 작업 종료 시 Stop 훅이 자동 갱신하며, 지금 갱신하려면 "
                     "`python3 .claude/hooks/codemap.py` 로 갱신하세요.\n")
    except OSError:
        pass

    log_event(cwd, "codemap_session", "docs/codemap.md", "loaded")
    print("=== 프로젝트 코드맵 (세션 시작 시 자동 로드) ===")
    if len(content) <= MAX_INLINE_CHARS:
        print(content)
    else:
        # 너무 크면 헤더와 디렉터리 목록만 추리고 전체는 참조하게
        lines = content.splitlines()
        head = []
        for l in lines:
            if l.startswith("## "):
                head.append(l)
        print("\n".join(lines[:12]))
        print("\n(코드맵이 커서 디렉터리 목록만 표시합니다. 전체는 docs/codemap.md 참조)")
        print("\n".join(head))
    print(stale)
    sys.exit(0)


if __name__ == "__main__":
    main()
