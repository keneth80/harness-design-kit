---
name: architect
description: spec.md 또는 prd.md를 기준으로 architect 에이전트가 빌드 설정, 도메인 엔티티, 공유 타입 골격을 만든다. 빌드·설치·타입체크가 통과하는 시작점을 보장한다.
when_to_use: 스캐폴딩, 프로젝트 골격, 빌드 설정, 공유 타입, dev 단계 직전.
disable-model-invocation: true
---

# 스캐폴딩

1. 입력: `docs/spec.md`를 단일 진실 원천으로 쓴다. 없고 `docs/prd.md`만 있으면 PRD에서 데이터 모델·엔드포인트를 직접 뽑는다.
   둘 다 없으면 `/harness-full:plan-start`부터 하라고 안내한다.
2. `harness-full:architect`에 위임: "빌드 설정, 도메인 엔티티, 공유 타입 골격을 만들고 build/install/typecheck가 통과하는 상태로 끝내줘".
3. architect가 남긴 `_workspace/01_architect_report.md`를 요약해 보고한다.
4. 다음 단계: UI가 있으면 `/harness-full:ui-design`, 없으면 `/harness-full:test-cases`.

주의
- architect는 비즈니스 로직을 쓰지 않는다. 빌드 설정과 빈 골격까지만.
- 빌드가 깨진 채 끝났으면 dev 에이전트에 넘기지 않고 architect가 다시 시도한다.
