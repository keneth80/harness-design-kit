---
name: qa-boundary
description: qa-engineer 에이전트로 모듈 사이 경계(백엔드 응답 ↔ 프론트 타입, 화면 ↔ API 매핑, 상태 UI 3종)를 검증한다. 모듈 하나가 끝날 때마다 점진적으로 부른다.
when_to_use: 경계 검증, API와 타입 맞는지, 화면과 API 매핑, 모듈 하나 완료 후.
argument-hint: "[기능ID | 모듈]"
disable-model-invocation: true
---

# 경계 검증

1. 대상: 인자(`$ARGUMENTS`)의 기능 ID·모듈, 없으면 `_workspace/02_*_report.md`에서 가장 최근 완료된 모듈, 그것도 없으면 git diff 영역.
2. `harness-full:qa-engineer`에 위임: 백엔드 응답 모델 ↔ 프론트 TS 타입, 화면 ↔ API 매핑, 로딩·빈·에러 상태 UI 구현 여부를 보고
   `_workspace/04_qa_engineer_report.md`에 누적 기록한다.
3. HIGH 이슈는 책임 에이전트와 함께 요약한다 (예: "BOUNDARY-001 HIGH → backend-dev: 응답 필드 camelCase 통일").
4. 사용자가 동의하면 책임 에이전트에게 수정을 맡긴다.

전체 완료를 기다리지 말고 모듈마다 부른다. code-verifier 통과와는 다른 관점의 검사다.
