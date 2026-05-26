---
name: verify
description: 검증 단계 실행. code-verifier 에이전트를 호출하여 변경된 코드를 test-cases.md 기준으로 다층 검증하고 verification-report.md를 생성한다.
---

코드 검증 단계를 시작합니다.

## 절차

1. code-verifier 에이전트에게 위임:
   - "code-verifier를 호출하여 변경된 코드를 검증해주세요"

2. code-verifier는 Haiku 모델로 동작합니다 (메인 세션과 다른 모델로 self-bias 제거).

3. 다음 3개 레이어로 검증합니다:
   - Layer A: 정적 분석 (linter, type checker, security scanner)
   - Layer B: 테스트 실행 (test-cases.md 기반)
   - Layer C: spec.md 일치성 + 보안/성능 의심 검토

4. 결과는 `docs/verification-report.md`에 저장됩니다.

5. 실패 케이스가 있으면 어느 dev 에이전트에게 무엇을 수정 요청할지 권장사항이 함께 제공됩니다.
