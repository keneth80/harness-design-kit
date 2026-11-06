#!/usr/bin/env python3
"""scenario_run: harness.scenarios.json의 시나리오를 needs 순서대로 확인한다.

  python3 scenario_run.py                    전부
  python3 scenario_run.py --only deploy      id나 태그로 고르기 (needs도 함께 돈다)
  python3 scenario_run.py --list             실행하지 않고 순서와 의존만 보기

출력은 JSON. 종료 코드: 0 = 선택한 시나리오 모두 pass, 1 = 하나라도 아님, 2 = 파일 오류.
원장에 묶으려면 harness.config.json에 "verify": {"scenarios": true} (또는 ["local"]처럼 id·태그 목록).
그러면 verify_run.py·backpressure·fix-until-green·/goal이 시나리오까지 통과해야 pass로 본다.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="쉼표로 구분한 id나 태그")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--timeout", type=int, default=60, help="command 검사 기본 타임아웃(초)")
    ap.add_argument("--project", default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    args = ap.parse_args()
    proj = os.path.abspath(args.project)
    cfg = _lib.load_config(proj)
    try:
        if args.list:
            order = _lib.load_scenarios(proj, cfg)
            print(json.dumps([{"id": s["id"], "then": s.get("then", ""), "needs": s.get("needs") or [],
                               "tags": s.get("tags") or [], "type": s["check"]["type"], "risk": bool(s.get("risk"))}
                              for s in order], ensure_ascii=False, indent=2))
            return
        only = [x for x in args.only.split(",") if x] or None
        res = _lib.run_scenarios(proj, only=only, timeout=args.timeout, cfg=cfg)
    except _lib.ScenarioError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(2)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    sys.exit(0 if res["passed"] else 1)


if __name__ == "__main__":
    main()
