#!/usr/bin/env python3
"""audit_report: 하네스 감사 로그(audit.jsonl) 요약.

deny/ask/error는 항상 기록되고, pass/warn은 HARNESS_MONITOR=1일 때만 기록된다.
로그는 프로젝트가 아니라 플러그인 데이터 디렉터리(~/.claude/plugins/data/harness-core-*/)에 있다.

사용: python3 audit_report.py [--data DIR] [--project PATH] [--all] [--days N]
"""
import argparse
import datetime
import glob
import json
import os
from collections import Counter, defaultdict


def find_logs(data_dir):
    cands = []
    if data_dir and not data_dir.startswith("${"):
        cands.append(os.path.join(data_dir, "audit.jsonl"))
    home = os.path.expanduser("~")
    cands += glob.glob(os.path.join(home, ".claude", "plugins", "data", "harness-*", "audit.jsonl"))
    cands.append(os.path.join(home, ".claude", "harness-data", "audit.jsonl"))
    seen, out = set(), []
    for c in cands:
        real = os.path.realpath(c)
        if real not in seen and os.path.isfile(real):
            seen.add(real)
            out.append(real)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="")
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--all", action="store_true", help="모든 프로젝트")
    ap.add_argument("--days", type=int, default=14)
    args = ap.parse_args()

    logs = find_logs(args.data)
    if not logs:
        print("감사 로그가 없습니다. 아직 차단·확인 이벤트가 없었거나, 통과 이벤트까지 보려면 "
              "`HARNESS_MONITOR=1 claude`로 실행하세요.")
        return

    since = (datetime.datetime.now() - datetime.timedelta(days=args.days)).isoformat()
    proj = os.path.realpath(args.project)
    events = []
    for log in logs:
        with open(log, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("ts", "") < since:
                    continue
                if not args.all and os.path.realpath(e.get("project") or "") != proj:
                    continue
                events.append(e)

    scope = "모든 프로젝트" if args.all else proj
    if not events:
        print(f"최근 {args.days}일간 이벤트가 없습니다 ({scope}).")
        return

    print(f"=== 하네스 감사 요약 · 최근 {args.days}일 · {scope} · {len(events)}건 ===\n")
    by_hook = defaultdict(Counter)
    for e in events:
        by_hook[e.get("hook", "?")][e.get("result", "?")] += 1
    print("훅별 결과")
    for hook in sorted(by_hook):
        c = by_hook[hook]
        print(f"  {hook:16} {sum(c.values()):4}건  " + ", ".join(f"{k} {v}" for k, v in c.most_common()))

    notable = [e for e in events if e.get("result") in ("deny", "ask", "block", "error")]
    if notable:
        print(f"\n차단·확인·오류 최근 {min(12, len(notable))}건")
        for e in notable[-12:]:
            print(f"  {e.get('ts', '')}  {e.get('hook')}  {e.get('result'):5}  {e.get('target', '')[:70]}")
            if e.get("reason"):
                print(f"      └ {e['reason'][:140]}")

    reasons = Counter(e.get("reason", "")[:60] for e in notable if e.get("reason"))
    if reasons:
        print("\n자주 걸린 사유")
        for r, n in reasons.most_common(5):
            print(f"  {n:3}회  {r}")


if __name__ == "__main__":
    main()
