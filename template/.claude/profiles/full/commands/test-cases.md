---
name: test-cases
description: 테스트 케이스 작성 단계 시작. docs/spec.md를 읽고 qa-tester 에이전트를 호출하여 test-cases.md와 tests/ 디렉토리의 테스트 코드를 생성한다.
---

테스트 케이스 작성 단계를 시작합니다.

## 절차

1. `docs/spec.md`가 존재하는지 확인합니다.
   - 없으면 "/plan-start 명령으로 기획 단계를 먼저 완료해주세요"라고 안내.

2. qa-tester 에이전트에게 위임:
   - "qa-tester를 호출하여 docs/spec.md 기반으로 test-cases.md와 tests/ 코드를 생성해주세요"

3. qa-tester는 Haiku 모델로 동작합니다. spec.md의 모든 기능 ID에 대해 테스트 케이스를 설계하고 코드를 작성합니다.

4. 작성 완료 후 사용자에게 다음 단계 안내:
   - "이제 frontend-dev / backend-dev로 구현 단계로 진행 가능합니다"
   - "구현 후 /verify 명령으로 검증 가능합니다"
