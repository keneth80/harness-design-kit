---
name: test-cases
description: spec.md의 모든 기능 ID에 대해 qa-tester 에이전트(haiku)가 docs/test-cases.md와 tests/ 테스트 코드를 만든다.
when_to_use: 테스트 케이스 작성, 테스트 설계, 구현 전 테스트, 인수 기준.
disable-model-invocation: true
---

# 테스트 케이스 작성

1. `docs/spec.md`가 없으면 `/harness-full:plan-start`부터 하라고 안내한다.
2. `harness-full:qa-tester`에 위임해 `docs/test-cases.md`와 `tests/` 코드를 만든다.
3. 다음 단계 안내: backend-dev·frontend-dev로 구현 → 모듈마다 `/harness-full:qa-boundary` → 끝나면 `/harness-core:verify`.
