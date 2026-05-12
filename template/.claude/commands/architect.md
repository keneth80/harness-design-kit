---
name: architect
description: architect 에이전트를 호출하여 빌드 설정, 도메인 엔티티, 공유 타입 스캐폴딩을 생성한다. spec.md 또는 prd.md 작성 후 dev 단계 직전에 호출. 빌드 통과를 보장하는 시작점을 만든다.
---

지금부터 architect 에이전트로 프로젝트 스캐폴딩을 만듭니다.

## 절차

1. **입력 문서 확인**:
   - `docs/spec.md`가 있으면 그것을 단일 진실 원천으로 사용.
   - `docs/spec.md`가 없고 `docs/prd.md`가 있으면 PRD 직접 진입 모드 — architect가 PRD에서 데이터 모델/엔드포인트를 직접 추출.
   - 둘 다 없으면 "기획부터 필요합니다. /plan-start로 ui-planner를 먼저 호출하세요"라고 안내.

2. architect 에이전트에게 위임:
   - "architect를 호출하여 {spec.md 또는 prd.md} 기반으로 빌드 설정, 도메인 엔티티, 공유 타입 스캐폴딩을 만들어주세요. 빌드/install/typecheck가 통과하는 상태로 끝내야 합니다."

3. architect가 작업 보고서(`_workspace/01_architect_report.md`)를 남기면 그 내용을 요약해서 사용자에게 보고.

4. 사용자에게 다음 단계 안내:
   - UI 있는 프로젝트: "다음은 /ui-design (있으면 건너뜀)과 /test-cases입니다."
   - UI 없는 프로젝트: "다음은 /test-cases로 테스트 케이스 작성입니다."
   - 사용자가 바로 구현 가능한 상태인지 확인.

## 주의

- architect는 비즈니스 로직을 구현하지 않습니다 — 빌드 설정과 빈 골격만.
- 빌드가 깨진 채로 끝났다면 architect가 다시 시도해야 함. dev 에이전트에게 인계 금지.
