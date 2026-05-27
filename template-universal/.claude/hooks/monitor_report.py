#!/usr/bin/env python3
"""
monitor_report: .claude/monitor.log를 읽어 하네스 훅 동작을 요약한다.
HARNESS_MONITOR=1로 켜둔 동안 쌓인 훅 발동 기록을 보기 좋게 정리.

사용: python3 monitor_report.py [프로젝트경로]  (기본: 현재 디렉터리)
"""
import sys, os, json
from collections import Counter, defaultdict

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    log = os.path.join(root, ".claude", "monitor.log")
    if not os.path.exists(log):
        print("모니터 로그가 없습니다. `export HARNESS_MONITOR=1` 로 켠 뒤 하네스를 사용하세요.")
        return

    events = []
    with open(log, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: events.append(json.loads(line))
            except Exception: pass

    if not events:
        print("로그가 비어 있습니다.")
        return

    print(f"=== 하네스 모니터링 요약 (총 {len(events)}건) ===\n")

    # 훅별 발동 횟수 + 결과 분포
    by_hook = defaultdict(Counter)
    for e in events:
        by_hook[e.get("hook","?")][e.get("result","?")] += 1

    print("훅별 발동 / 결과:")
    for hook in sorted(by_hook):
        results = by_hook[hook]
        total = sum(results.values())
        detail = ", ".join(f"{r}:{c}" for r, c in results.most_common())
        print(f"  {hook:18} {total}회  ({detail})")

    # 주목할 이벤트: 차단/실패
    notable = [e for e in events if e.get("result") in ("blocked", "fail")]
    if notable:
        print(f"\n주목 이벤트 (차단/실패 {len(notable)}건):")
        for e in notable[-10:]:  # 최근 10건
            print(f"  [{e.get('ts','')}] {e.get('hook')} → {e.get('result')} ({e.get('target','')})")

    # 최근 활동
    print(f"\n최근 5건:")
    for e in events[-5:]:
        print(f"  [{e.get('ts','')}] {e.get('hook')} {e.get('result')} {e.get('target') or ''}")

if __name__ == "__main__":
    main()
