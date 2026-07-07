---
name: plan-start
description: 프로젝트 기획 단계 시작. docs/goal.md 또는 docs/prd.md를 읽고 ui-planner 에이전트를 호출하여 requirements.md와 spec.md를 작성한다. PRD 직접 진입 모드도 지원.
---

지금부터 이 프로젝트의 기획 단계를 시작합니다.

## 절차

1. **입력 문서 확인** (우선순위 순):
   - `docs/spec.md` 이미 있으면 → "이미 spec이 있습니다. 갱신할까요, 그대로 두고 다음 단계로 갈까요?"
   - `docs/prd.md` 있으면 → **PRD 직접 진입 모드**. ui-planner를 인터뷰 최소화 모드로 호출. 사용자에게 "PRD가 이미 있습니다. ui-planner로 spec.md를 추출하시겠습니까, 아니면 `/architect`로 바로 스캐폴딩 시작하시겠습니까?"라고 옵션 제시.
   - `docs/goal.md` 있으면 → 기존 흐름. ui-planner를 한 줄 목표 인터뷰 모드로 호출.
   - 셋 다 없으면 → "이 프로젝트는 간단 모드입니다. 풀 사이클로 진행하려면 docs/goal.md 또는 docs/prd.md를 작성하거나 scaffold.sh를 풀 사이클 모드로 다시 실행해주세요"라고 안내.

2. ui-planner 호출:
   - "ui-planner를 호출하여 {goal.md 또는 prd.md} 기반으로 requirements.md와 spec.md를 작성해주세요"

3. ui-planner가 사용자에게 추가 질문할 수 있습니다. 답변을 받아 다시 ui-planner에게 전달.

4. spec.md 작성 완료 후 사용자에게 다음 단계 안내:
   - 멀티스택 프로젝트: "/architect 명령으로 빌드 설정 + 도메인 엔티티 스캐폴딩으로 진행하시겠습니까?"
   - UI 있는 프로젝트: "/ui-design 명령으로 UI 설계 단계로 진행하시겠습니까?"
   - UI 없는 프로젝트(CLI/API): "/test-cases 명령으로 테스트 케이스 작성 단계로 진행하시겠습니까?"
