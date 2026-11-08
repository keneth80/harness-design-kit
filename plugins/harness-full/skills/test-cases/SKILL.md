---
name: test-cases
description: spec.md의 모든 기능 ID에 대해 docs/test-cases.md와 tests/ 테스트 코드를 만든다. 테스트 설계 에이전트(haiku)가 따로 떨어져 작업한다.
when_to_use: 테스트 케이스 작성, 테스트 설계, 구현 전 테스트, 인수 기준.
disable-model-invocation: true
context: fork
agent: harness-full:qa-tester
---

다음을 순서대로 수행한다.

1. `docs/spec.md`가 없으면 작업하지 말고 "`/harness-full:plan-start`부터 하세요"라고 돌려준다.
2. 미리 불러온 test-design-playbook 절차대로 기능 ID마다 테스트 케이스를 `docs/test-cases.md`에 쓰고 `tests/`에 테스트 코드를 만든다.
3. 마지막 답변: 기능 ID별 케이스 수, 만든 파일, 다음 단계(구현 → 모듈마다 `/harness-full:qa-boundary` → `/harness-core:verify`).
