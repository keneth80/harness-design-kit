---
name: qa-boundary
description: qa-engineer 에이전트를 호출하여 모듈 사이의 boundary(API 응답 ↔ TS 타입, 화면 ↔ API 매핑)를 검증한다. 모듈이 하나 끝날 때마다 progressive하게 호출.
---

지금부터 qa-engineer로 boundary 검증을 수행합니다.

## 절차

1. **검증 대상 식별**:
   - 사용자가 명시한 모듈/기능 ID (예: "F1만 검증")
   - 또는 _workspace/02_backend_report.md, 02_frontend_report.md를 보고 가장 최근 완료된 모듈
   - 또는 git diff로 최근 변경된 영역

2. qa-engineer에게 위임:
   - "qa-engineer를 호출하여 {모듈 이름}의 boundary를 검증해주세요. 백엔드 응답 모델 ↔ 프론트 TS 타입 일치, 화면 ↔ API 매핑, 상태 UI 3가지 구현 여부를 확인하고 _workspace/04_qa_engineer_report.md에 누적 기록해주세요."

3. qa-engineer 보고서의 HIGH 이슈를 사용자에게 요약 + 책임 에이전트 명시:
   - "BOUNDARY-001 HIGH: backend-dev에게 응답 필드명 camelCase 통일 요청"
   - "BOUNDARY-002 MEDIUM: frontend-dev에게 nullable 처리 추가 요청"

4. 사용자가 수정 위임에 동의하면 책임 에이전트 호출.

## 호출 시점

- 모듈 하나가 완료된 직후 (전체 완료를 기다리지 마세요).
- spec.md / ui-spec.md 변경 후 영향받는 모듈에 대해.
- code-verifier가 단위 검증을 통과했더라도 별도로 qa-boundary 필요 (다른 관점).
