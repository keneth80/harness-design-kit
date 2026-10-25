---
name: audit
description: 하네스 훅의 감사 로그를 요약한다. 어떤 게이트가 무엇을 왜 막았는지(deny/ask), 오류가 있었는지, 자주 걸리는 사유가 무엇인지 보여준다. v1의 /monitor와 /verify-report를 대체한다.
when_to_use: 하네스가 뭘 막았지, 왜 차단됐어, 훅 기록, 감사 로그, 모니터링.
argument-hint: "[--all] [--days N]"
disable-model-invocation: true
---

# 하네스 감사 요약

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit_report.py" --data "${CLAUDE_PLUGIN_DATA}" --project "$PWD" $ARGUMENTS
```

- 차단(deny)·확인(ask)·오류(error)는 항상 기록된다. 통과·경고까지 보려면 `HARNESS_MONITOR=1 claude`로 실행한다.
- 로그는 프로젝트가 아니라 플러그인 데이터 디렉터리에 쌓인다(저장소를 더럽히지 않음).
- 결과를 그대로 전달하고, 같은 사유가 반복되면 원인(오탐인지, 습관적 우회 시도인지)을 짧게 짚는다.
  오탐이면 `harness.config.json`의 `security.allow_paths` 같은 조정안을 제안한다.
