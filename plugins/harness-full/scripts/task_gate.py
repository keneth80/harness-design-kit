#!/usr/bin/env python3
"""task_gate: TaskCompleted (harness-full).

에이전트 팀의 팀원이 작업을 "완료"로 표시하려 할 때, 린트·타입체크가 깨져 있으면 완료를 막고 이유를 돌려준다.
팀 밖(혼자 쓰는 할 일 목록)에서는 아무것도 하지 않는다. 할 일 하나 끝날 때마다 검사를 돌리면 너무 느리기 때문이다.

- 입력: task_id, task_subject, task_description, teammate_name, team_name
- 차단: exit 2 + stderr (TaskCompleted의 계약)
- 테스트는 돌리지 않는다 (느림). 테스트는 종료 시 backpressure가 맡는다.
- 끄기: harness.config.json의 "task_gate": {"enabled": false}
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402
from backpressure import autodetect  # noqa: E402

HOOK = "task_gate"


def main():
    event = _lib.read_event()
    if not (event.get("teammate_name") or "").strip():
        sys.exit(0)
    proj = _lib.project_dir(event)
    if not _lib.is_initialized(proj):
        sys.exit(0)
    cfg = _lib.load_config(proj)
    if not (cfg.get("task_gate") or {}).get("enabled", True):
        sys.exit(0)

    vcfg = dict(cfg.get("verify") or {})
    if not any(vcfg.get(k) for k in ("lint", "typecheck")):
        vcfg = autodetect(proj)
    checks = [(k, vcfg[k]) for k in ("lint", "typecheck") if vcfg.get(k)]
    if not checks:
        sys.exit(0)

    failures = []
    for key, cmd in checks:
        try:
            r = subprocess.run(cmd, shell=True, cwd=proj, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            failures.append(f"[{key}] `{cmd}` 시간 초과")
            continue
        if r.returncode != 0:
            tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-15:]
            failures.append(f"[{key}] `{cmd}` 실패 (exit {r.returncode})\n" + "\n".join(tail))

    subject = event.get("task_subject") or event.get("task_id") or "작업"
    if failures:
        _lib.audit(proj, HOOK, "block", subject, failures[0][:300])
        print(f"[task_gate] '{subject}'을 완료로 표시하기 전에 검증을 통과시켜야 합니다.\n\n" + "\n\n".join(failures),
              file=sys.stderr)
        sys.exit(2)
    _lib.audit(proj, HOOK, "pass", subject)
    sys.exit(0)


if __name__ == "__main__":
    main()
