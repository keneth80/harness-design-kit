---
name: monitor
description: 하네스 훅의 동작 기록(monitor.log)을 요약해 보여준다. HARNESS_MONITOR=1로 켠 동안 어떤 훅이 몇 번 발동했고 차단/실패가 있었는지 확인.
---

하네스 모니터링 로그를 요약해서 보여주세요.

```bash
python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/monitor_report.py" "$CLAUDE_PROJECT_DIR"
```

결과를 사용자에게 그대로 전달하세요. 로그가 없다고 나오면, 모니터링을 켜는 방법을 안내하세요:
`export HARNESS_MONITOR=1` 을 실행한 뒤(또는 셸 프로파일에 추가) 하네스를 사용하면 훅 동작이 기록됩니다.
끄려면 `unset HARNESS_MONITOR`.
