#!/usr/bin/env python3
"""harness-core의 scripts/_lib.py를 다른 플러그인으로 복사한다.

플러그인은 설치 후 서로의 디렉터리를 참조할 수 없어서(각자 캐시 경로가 다름) 공통 모듈을 사본으로 둔다.
원본은 plugins/harness-core/scripts/_lib.py 하나뿐이다. 사본을 직접 고치지 말고 원본을 고친 뒤 이 스크립트를 돌린다.
tests/test_layout.py가 사본이 원본과 같은지 검사한다.

사용: python3 tools/sync_lib.py [--check]
"""
import filecmp
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "plugins", "harness-core", "scripts", "_lib.py")
TARGETS = [os.path.join(ROOT, "plugins", p, "scripts", "_lib.py") for p in ("harness-full", "harness-codex")]


def main():
    check = "--check" in sys.argv
    stale = [t for t in TARGETS if not os.path.exists(t) or not filecmp.cmp(SOURCE, t, shallow=False)]
    if check:
        for t in stale:
            print(f"다름: {os.path.relpath(t, ROOT)}")
        sys.exit(1 if stale else 0)
    for t in stale:
        os.makedirs(os.path.dirname(t), exist_ok=True)
        shutil.copyfile(SOURCE, t)
        print(f"갱신: {os.path.relpath(t, ROOT)}")
    if not stale:
        print("모든 사본이 최신입니다.")


if __name__ == "__main__":
    main()
