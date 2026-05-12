---
name: orchestrator
trigger: "{{ORCHESTRATOR_TRIGGER}}"
---

# {{PROJECT_NAME}} Orchestrator

> **이 스킬은 도메인 비종속 골격입니다.** scaffold.sh가 풀 사이클 모드로 프로젝트를 만들 때 이 파일을 `{{PROJECT_NAME}}-orchestrator/SKILL.md`로 복사하면서 `{{}}` 변수들을 채웁니다. 본체는 `template/.claude/skills/orchestrator/`에 그대로 남기고, 프로젝트 인스턴스만 도메인 특화 트리거를 갖습니다.

## 역할

이 스킬은 풀 사이클 워크플로우의 **에이전트 팀 오케스트레이션**을 담당합니다. 4~5개 에이전트(architect, backend-dev, frontend-dev, qa-tester, qa-engineer)를 의존성에 맞게 호출하고 진행 상황을 `_workspace/`에 기록합니다.

호출 트리거: `{{ORCHESTRATOR_TRIGGER}}` 키워드가 사용자 요청에 포함되거나, `/plan-start` 이후 메인 세션이 위임할 때.

## 입력

- `docs/spec.md` 또는 `docs/prd.md` (필수)
- `docs/ui-spec.md`, `docs/test-cases.md` (있으면 활용)
- `_workspace/` 기존 보고서 (이어하기 모드 판단용)

## Phase 0 — 컨텍스트 체크

`_workspace/` 디렉토리를 읽어 실행 모드를 판단합니다:

| 상태 | 모드 |
|---|---|
| `_workspace/` 비어있음 | **initial** — 처음부터 |
| `_workspace/01_architect_report.md` 있음 + `02_*` 없음 | **post-architect** — dev 단계부터 |
| `02_*_report.md` 일부만 있음 | **partial** — 미완 모듈만 재실행 |
| 모든 보고서 + verification-report.md PASS | **closeout** — 마무리만 |

`_workspace/00_context_snapshot.md`에 판단 결과와 다음 액션을 기록.

## Phase 1 — 준비

1. `docs/spec.md` (또는 `docs/prd.md`)를 읽고 다음을 추출:
   - 기능 ID 목록 (F1, F2, ...)
   - API 엔드포인트 목록
   - 화면 ID 목록 (UI 있는 경우)
2. 사용자에게 다음을 한 번에 확인:
   - 진행할 모듈 우선순위 (모든 F를 한꺼번에? 아니면 F1부터 순차?)
   - 데모 데이터 사용 여부
   - 외부 API 키 준비 상태
3. `_workspace/00_context_snapshot.md`에 응답 기록.

## Phase 2 — 팀 셋업 + 작업 분배

다음 작업을 의존성과 함께 등록합니다:

| ID | 작업 | 담당 | blockedBy |
|---|---|---|---|
| T01 | 빌드 설정 + 도메인 엔티티 | architect | (없음) |
| T02 | UI 와이어프레임 + ui-spec.md | ui-designer | (UI 있는 경우만) |
| T03 | test-cases.md + tests/ 골격 | qa-tester | T01 |
| T04 | 백엔드 모듈 1 (F1) | backend-dev | T01 |
| T05 | 백엔드 모듈 2 (F2) | backend-dev | T01 |
| T06 | 프론트엔드 화면 1 (ScreenA) | frontend-dev | T01, T02 |
| T07 | 프론트엔드 화면 2 (ScreenB) | frontend-dev | T01, T02 |
| T08 | Boundary 검증 (F1/ScreenA) | qa-engineer | T04, T06 |
| T09 | Boundary 검증 (F2/ScreenB) | qa-engineer | T05, T07 |
| T10 | 통합 검증 + 데모 시연 | code-verifier | T03~T09 |

기능 ID와 화면 ID 수에 맞춰 동적으로 행을 늘립니다.

## Phase 3 — 실행

- T01 architect 먼저 단독 실행 (블로킹).
- T01 완료 후 T02 + T03을 병렬, 그리고 T04~T07을 의존성 만족하는 즉시 병렬 실행.
- 각 backend/frontend 모듈이 끝날 때마다 즉시 qa-engineer(T08, T09...)를 호출 — **완료를 기다리지 않고 progressive**.
- code-verifier는 코드 변경 직후 자동 호출되므로 별도 트리거 불필요.

진행 상황은 각 에이전트가 자기 보고서(`_workspace/02_backend_report.md` 등)에 누적합니다. 메인 세션은 보고서를 읽으면 어디까지 됐는지 즉시 파악 가능.

## Phase 4 — 통합 검증

모든 모듈 완료 후:

1. `docs/verification-report.md` (code-verifier 산출)와 `_workspace/04_qa_engineer_report.md` (qa-engineer 산출)를 동시에 검토.
2. HIGH 이슈가 남아있으면 책임 에이전트에게 수정 요청 후 재검증.
3. 데모 시연 시나리오 실행:
   - 빌드/install이 깨끗한 환경에서 한 번에 통과하는지
   - `docs/spec.md`에 명시된 사용자 시나리오 1건 이상 end-to-end로 동작하는지

## Phase 5 — 마무리

1. `_workspace/05_session_log.md`에 의사결정 요약 기록.
2. 사용자에게 결과 보고:
   - 구현된 기능 ID 목록
   - 실행 방법 (`make demo` 또는 `npm run dev` 등)
   - 알려진 한계 / TODO
3. `_workspace/`는 보존 (다음 세션의 컨텍스트).

## 에이전트 간 통신

- **상태 공유**: 각자 `_workspace/{NN}_*.md`에 쓰고 다른 에이전트는 읽음. 채팅 형식 메시지 대신 보고서 파일이 진실의 원천.
- **API shape 코디네이션**: architect의 `shared/types/`가 단일 소스. backend가 응답 모델을 바꾸면 같은 PR 안에서 `shared/types/`도 갱신해야 함.
- **버그 보고**: qa-engineer가 발견하면 BOUNDARY-NNN 번호로 보고서에 기록 + 메인 세션에 통보. 메인 세션이 책임 에이전트에게 위임.

## 에러 처리

- **architect 빌드 실패**: 본인이 수정. 두 번 실패 시 사용자에게 스택 결정 재확인 요청.
- **외부 API 미준비**: mock/demo 모드로 폴백 후 진행. `_workspace/`에 "실제 API 키 필요" 마킹.
- **에이전트 응답 없음**: 30초 이상 무응답이면 메인 세션이 작업 재할당.
- **명세 충돌**: 두 에이전트가 서로 다른 인터페이스를 만들었으면 spec.md를 단일 진실 원천으로 다시 정렬, qa-engineer가 boundary 검증.

## 절대 어기지 말 것

- spec.md / prd.md 없이 풀 사이클 시작 금지 — ui-planner부터 호출.
- architect 빌드 실패한 채로 dev 호출 금지.
- 모든 모듈 완료를 기다리지 말고 progressive하게 qa-engineer 호출.
- 같은 모델끼리 self-verify 금지 — code-verifier/qa-engineer는 haiku 강제.
