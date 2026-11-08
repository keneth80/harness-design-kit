---
name: qa-boundary
description: 모듈 사이 경계(백엔드 응답과 프론트 타입, 화면과 API 매핑, 로딩·빈·에러 상태)를 검증한다. 경계 검증 에이전트(haiku)가 따로 떨어져 읽기 전용으로 본다. 모듈 하나가 끝날 때마다 부른다.
when_to_use: 경계 검증, API와 타입 맞는지, 화면과 API 매핑, 모듈 하나 완료 후.
argument-hint: "[기능ID | 모듈]"
disable-model-invocation: true
context: fork
agent: harness-full:qa-engineer
---

다음을 순서대로 수행한다. 코드는 고치지 않는다.

1. 대상: `$ARGUMENTS`의 기능 ID나 모듈. 비어 있으면 `_workspace/02_*_report.md`에서 가장 최근 완료된 모듈, 그것도 없으면 `git diff HEAD` 영역.
2. 미리 불러온 boundary-playbook 절차대로 백엔드 응답 모델과 프론트 타입, 화면과 API 매핑, 로딩·빈·에러 상태 UI를 대조한다.
3. 결과를 `_workspace/04_qa_engineer_report.md`에 누적 기록한다.
4. 마지막 답변: HIGH 이슈마다 번호, 내용, 책임(backend-dev 또는 frontend-dev), 수정 제안 한 줄. MEDIUM 이하는 개수만.
