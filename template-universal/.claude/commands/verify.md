---
name: verify
description: 검증 단계 실행. code-verifier 에이전트를 호출하여 변경된 코드를 test-cases.md 기준으로 다층 검증하고 verification-report.md를 생성한다. 자동 PostToolUse 코드 리뷰(구 code_reviewer 훅)를 대체하는 온디맨드 검증 진입점.
---

코드 검증 단계를 시작합니다.

## 절차

1. code-verifier 에이전트에게 위임:
   - "code-verifier를 호출하여 변경된 코드를 검증해주세요"

2. code-verifier는 Haiku 모델로 동작합니다 (메인 세션과 다른 모델로 self-bias 제거).

3. 다음 4개 레이어로 검증합니다:
   - Layer A: 정적 분석 (linter, type checker, security scanner)
   - Layer B: 테스트 실행 (test-cases.md 기반)
   - Layer C: spec.md 일치성 + 보안/성능 의심 검토
   - Layer D: 변경 diff 코드 리뷰 — 구 PostToolUse code_reviewer 훅의 역할.
     보안(하드코딩 시크릿·API키·private key, eval(), f-string SQL injection 패턴),
     성능, 맥락(주변 코드와의 일관성) 3차원을 변경된 파일에 대해 점검한다.

4. 결과는 `docs/verification-report.md`에 저장됩니다.

5. 실패 케이스가 있으면 어느 dev 에이전트에게 무엇을 수정 요청할지 권장사항이 함께 제공됩니다.

> 참고: lite 프로파일에서는 매 수정마다 자동 리뷰가 발동하지 않으므로,
> 작업 단위가 끝날 때마다 이 커맨드로 검증하는 것을 권장합니다.
