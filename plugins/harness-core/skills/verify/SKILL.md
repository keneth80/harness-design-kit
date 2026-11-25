---
name: verify
description: code-verifier 에이전트(haiku)로 변경된 코드를 정적 분석·테스트·스펙·교훈 기준으로 검증한다.
when_to_use: 검증해줘, 다 됐는지 확인, 커밋·PR 전 점검.
argument-hint: "[경로 | 기능ID]"
---

# 검증

편집할 때마다 도는 verify_guard(린트·타입체크)와 달리, 이 스킬은 **작업 단위가 끝났을 때** 깊게 본다.

## 절차

1. 범위: 인자(`$ARGUMENTS`)가 있으면 그 경로·기능 ID로 한정한다. 없으면 `git diff HEAD` 기준 변경 전체.
2. `harness-core:code-verifier` 에이전트에게 위임한다: "변경된 코드를 4개 레이어로 검증하고 docs/verification-report.md를 작성해줘".
   - Layer A 정적 분석: 프로젝트의 린터·타입체커·보안 스캐너
   - Layer B 테스트: `docs/test-cases.md`가 있으면 그 기준으로, 없으면 기존 테스트 스위트
   - Layer C 스펙 일치: `docs/spec.md`, 도메인 매뉴얼(`docs/domains/*/manual.md`)과 대조
   - Layer D 교훈·diff 리뷰: `docs/lessons-learned.md`의 모든 L 엔트리 위반 + 보안(하드코딩 시크릿, eval, 문자열 SQL)·성능·맥락 일관성
3. 리포트 맨 위의 원장 상태(`verify_run.py`의 state)를 그대로 옮긴다. pass가 아니면 통과로 보고하지 않는다.
4. 결과를 요약해 보고한다. 실패 항목마다 어떤 파일을 누가(어떤 dev 에이전트가) 고쳐야 하는지 함께 적는다.
5. 같은 유형의 실패가 반복되면 `/harness-core:lessons`로 교훈 승격을 제안한다.
