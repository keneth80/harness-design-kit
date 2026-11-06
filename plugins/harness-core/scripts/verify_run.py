#!/usr/bin/env python3
"""verify_run: 검사를 직접 돌리고 서명한 통과 기록(원장)을 남긴다.

루프와 워크플로우가 "통과"를 판단할 때 에이전트의 보고 대신 이 원장을 믿는다.

  python3 verify_run.py                 harness.config.json의 verify(lint, typecheck, test)를 돌리고 원장을 쓴다
  python3 verify_run.py --cmd "pytest"  이 명령 하나만 돌린다 (원장 상태는 partial-pass까지만)
  python3 verify_run.py --status        원장만 확인한다 (검사를 돌리지 않음)

출력은 JSON 한 줄. 종료 코드: 0 = pass, 1 = 실패·오래됨·변조, 2 = 검증 명령 없음.
--cmd로 돌린 경우 그 명령이 통과하면 0.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

TAIL_LINES = 30
TAIL_CHARS = 4000


def run_checks(proj, checks, timeout):
    results = []
    for name, cmd in checks:
        start = time.monotonic()
        try:
            r = subprocess.run(cmd, shell=True, cwd=proj, capture_output=True, text=True, timeout=timeout)
            code, out = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            code, out = 124, f"시간 초과 ({timeout}s)"
        tail = "\n".join(out.strip().splitlines()[-TAIL_LINES:])[-TAIL_CHARS:]
        results.append({"name": name, "command": cmd, "exit": code,
                        "seconds": round(time.monotonic() - start, 1), "tail": tail})
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true", help="원장만 확인")
    ap.add_argument("--cmd", default="", help="설정 대신 이 명령 하나만 실행")
    ap.add_argument("--project", default="")
    args = ap.parse_args()

    proj = os.path.abspath(args.project or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    cfg = _lib.load_config(proj)

    if args.status:
        st = _lib.ledger_status(proj, cfg)
        print(json.dumps(st, ensure_ascii=False))
        sys.exit(0 if st["state"] == "pass" else 2 if st["state"] == "unconfigured" else 1)

    if args.cmd:
        checks, timeout = [("custom", args.cmd)], _lib.verify_checks(proj, cfg)[1]
    else:
        checks, timeout = _lib.verify_checks(proj, cfg)
    if not checks:
        print(json.dumps({"state": "unconfigured",
                          "hint": "harness.config.json의 verify(lint, typecheck, test)를 채우세요."}, ensure_ascii=False))
        sys.exit(2)

    results = run_checks(proj, checks, timeout)
    _lib.write_ledger(proj, results, cfg)
    st = _lib.ledger_status(proj, cfg)
    failures = [{"name": r["name"], "command": r["command"], "exit": r["exit"], "tail": r["tail"]}
                for r in results if r["exit"] != 0]
    print(json.dumps({**st, "failures": failures}, ensure_ascii=False))
    ok = st["state"] == "pass" or (args.cmd and st["state"] == "partial-pass")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
