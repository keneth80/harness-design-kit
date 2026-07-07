---
name: ui-design
description: UI 설계 단계 시작. docs/spec.md를 읽고 ui-designer 에이전트를 호출하여 mockup.md와 ui-spec.md를 작성한다. UI가 있는 프로젝트만 사용.
---

UI 설계 단계를 시작합니다.

## 절차

1. `docs/spec.md`가 존재하는지 확인합니다.
   - 없으면 "/plan-start 명령으로 기획 단계를 먼저 완료해주세요"라고 안내.

2. `docs/spec.md`에 화면 목록이 있는지 확인:
   - "화면 목록" 섹션이 비어있거나 도메인이 api/cli면 "이 프로젝트는 UI가 없습니다. /test-cases 명령으로 진행하세요"라고 안내.

3. ui-designer 에이전트에게 위임:
   - "ui-designer를 호출하여 docs/spec.md 기반으로 mockup.md와 ui-spec.md를 작성해주세요"

4. 작성 완료 후 사용자 검토 요청.

5. 사용자 승인 시 "/test-cases 명령으로 테스트 케이스 작성 단계로 진행하시겠습니까?"
