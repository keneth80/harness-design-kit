#!/usr/bin/env python3
"""
monitor: 하네스 훅 모니터링 공통 모듈.
환경변수 HARNESS_MONITOR=1 일 때만 동작한다. 안 켜져 있으면 아무것도 하지 않는다(오버헤드 0).

각 훅이 import해서 log_event(...)를 호출하면, 활성화 시 .claude/monitor.log에 한 줄 남긴다.
형식(JSON Lines): {"ts": ISO시각, "hook": 훅이름, "target": 대상파일, "result": 결과}

사용 예 (각 훅에서):
    from monitor import log_event
    log_event(cwd, "drift_guard", target_file, "blocked")
    log_event(cwd, "verify_guard", target_file, "pass")
"""
import os, json, datetime


def is_enabled():
    return os.environ.get("HARNESS_MONITOR", "").strip() in ("1", "true", "on", "yes")


def log_event(cwd, hook, target=None, result=None):
    """활성화 시에만 .claude/monitor.log에 이벤트 한 줄 기록. 실패해도 조용히 넘어간다."""
    if not is_enabled():
        return
    try:
        log_dir = os.path.join(cwd or os.getcwd(), ".claude")
        os.makedirs(log_dir, exist_ok=True)
        entry = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "hook": hook,
            "target": target,
            "result": result,
        }
        with open(os.path.join(log_dir, "monitor.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 모니터링 실패가 훅 동작을 막아선 안 된다
