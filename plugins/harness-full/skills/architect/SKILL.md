---
name: architect
description: spec.md 또는 prd.md를 기준으로 빌드 설정, 도메인 엔티티, 공유 타입 골격을 만든다. 빌드·설치·타입체크가 통과하는 시작점까지. 아키텍트 에이전트(opus)가 따로 떨어져 작업하고 결과만 돌려준다.
when_to_use: 스캐폴딩, 프로젝트 골격, 빌드 설정, 공유 타입, dev 단계 직전.
disable-model-invocation: true
context: fork
agent: harness-full:architect
---

다음을 순서대로 수행한다.

1. `docs/spec.md`를 단일 진실 원천으로 읽는다. 없고 `docs/prd.md`만 있으면 PRD에서 데이터 모델과 엔드포인트를 뽑는다. 둘 다 없으면 작업하지 말고 "`/harness-full:plan-start`부터 하세요"라고 돌려준다.
2. 미리 불러온 architect-playbook 절차대로 빌드 설정, 도메인 엔티티, 공유 타입 골격을 만든다. 비즈니스 로직은 쓰지 않는다.
3. build, install, typecheck가 통과할 때까지 고친다. 두 번 시도해도 안 되면 멈추고 원인을 적는다.
4. `_workspace/01_architect_report.md`를 쓴다.
5. 마지막 답변: 만든 것 요약, 빌드 통과 여부, 다음 단계(UI가 있으면 `/harness-full:ui-design`, 없으면 `/harness-full:test-cases`).
