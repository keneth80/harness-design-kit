# JARVIS Harness Kit

Claude Code 하네스 모음. 도메인 설계부터 구현·검증·세션 연속성까지 한 패키지로 묶었다.
"AI가 코딩하다 폭주하는 것"을 프롬프트가 아니라 **메커니즘(훅·스킬·계약 문서)으로 강제**하는 게 핵심.

## 한눈에

- **두 템플릿** — `template-universal`(범용) / `template`(JARVIS 브라우저 챗봇 특화).
  `scaffold.sh`로 현재 프로젝트에 깔거나, `jarvis-harness-plugin`으로 슬래시 커맨드 한 줄(`/harness-init`)로 설치.
- **도메인 설계 사이클** — 인터뷰로 모순 잡고, 매뉴얼로 규칙 박고, 코드가 규칙을 어기면 훅이 차단·경고.
- **검증 레이어** — 코드 수정 후 자동으로 타입체크·린트 실행(verify_guard).
- **코드맵** — 세션이 끊겨도 다음 세션이 코드 구조를 즉시 파악(SessionStart 자동 로드, Stop 시 자동 갱신).
- **모니터링** — `HARNESS_MONITOR=1` 켜면 어떤 훅이 몇 번 발동했는지 기록, `/monitor`로 요약.
- **모델 분배** — 설계=opus-4-7 / 구현=sonnet-4-6 / QA=haiku-4-5. 에이전트별로 박혀 있음.
- **관련 패키지** — `design-harness`(Claude 설계 + Codex 구현 분업) 별도 저장소.

## 템플릿 비교

| 항목 | `template-universal` (기본) | `template` (JARVIS 챗봇) |
|---|---|---|
| 에이전트 | 10개 기본 + 3개 optional | 동일 |
| 스킬 | 8개 + optional 2개 | 13개 (브라우저/챗봇 도메인 5개 추가) |
| 커맨드 | 15개 | 16개 (`/browser-status` 추가) |
| 룰 | 없음 | cdp-init, ws-protocol |
| 훅 | 11종 (양쪽 동일) | 동일 |
| CLAUDE.md | `{{PROJECT_NAME}}` 슬롯, 도메인 비종속 | JARVIS 도메인 박힘 |

## 에이전트 (10개 기본 + 3개 optional)

### 기본 (`.claude/agents/`)
- **architect** (opus-4-7) — 빌드 골격·도메인 엔티티·공유 타입 스캐폴딩.
- **ui-planner** (opus-4-7) — 요구사항·스펙·화면 ID 정의.
- **backend-dev** (sonnet-4-6) — FastAPI 등 백엔드 구현. 자체 코딩 규칙 보유.
- **frontend-dev** (sonnet-4-6) — React/Next 프론트 구현. 자체 코딩 규칙 보유.
- **ui-designer** (sonnet-4-6) — 화면 시각 구현(mockup, ui-spec).
- **error-handler** (sonnet-4-6) — 에러 진단·복구.
- **code-verifier** (haiku) — 다층 검증. 코딩 규칙 위반 점검 포함.
- **qa-engineer** (haiku) — 모듈 경계(API↔타입, 화면↔API) 비교 검증.
- **qa-tester** (haiku) — 테스트 케이스 작성.
- **error-curator** (haiku) — 에러 기록 정리, lessons-learned 큐레이션.

### Optional (`.claude/agents/optional/`)
도메인 따라 `scaffold.sh`가 자동 활성화 — automation→automation-dev, browser→browser-dev 등.
- **automation-dev**, **browser-dev**, **integration-dev** (모두 sonnet-4-6).

## 스킬

### 도메인 설계 사이클 (이번 하네스의 핵심)
- **domain-interview** — 도메인 발견 → 슬롯 인터뷰 → 모순 검출. `docs/domains/<domain>/interview.json`에 결정 기록.
- **domain-manual** — 인터뷰를 매뉴얼(불변 규칙·의존 계약)로 변환. `docs/domains/<domain>/manual.md`.
- **domain-refactor** — 매뉴얼 기준으로 코드 진단(기본 report 모드). 매뉴얼에 근거 없는 변경 금지.

### 범용 워크플로우
- **grill** — 코딩 전 요구사항 정렬 (질문 공세).
- **tdd** — vertical slice TDD.
- **diagnose** — 버그 재현→최소화→원인규명.
- **architecture** — 아키텍처 개선 (deep module, 복잡도/의존성).
- **orchestrator** — 풀 사이클 골격.

### optional (도메인 따라 자동 활성화)
- **browser-automation** — automation/video/youtube 도메인 시 활성화.
- **task-routing** — agent 도메인 시 활성화.

> 챗봇 템플릿은 위에 더해 **browser-automation, chatbot-ui, design-system, error-recovery, task-routing**을 기본 포함.

> 코딩 규범(karpathy 4원칙·네이밍·주석·보안 등)은 별도 스킬이 아니라 **CLAUDE.md에 전역 박혀** 있다.
> 항상 적용돼야 하는 상시 규범은 trigger 달린 스킬보다 CLAUDE.md가 정확한 자리이기 때문.

## 슬래시 커맨드 (15개, 도메인 비종속)

| 분류 | 커맨드 |
|---|---|
| 설계·기획 | `/grill`, `/plan-start`, `/architect`, `/ui-design` |
| 구현·테스트 | `/tdd`, `/test-cases`, `/diagnose` |
| 검증 | `/verify`, `/qa-boundary`, `/verify-report`, `/pr-review` |
| 보조 | `/commit`, `/dev-start`, `/lessons`, `/monitor` |

각 커맨드 frontmatter에 description이 있어 `/` 메뉴에서 설명을 본다.
챗봇 템플릿엔 `/browser-status` (CDP 인스턴스 점검) 추가.

## Hooks (11종, 양쪽 템플릿 공통)

### PreToolUse (사전 차단/검사)
- **security_gate** — Bash 명령 안전 검사.
- **drift_guard** — 코드 수정 전, "미완성 도메인 코드 수정" 차단(exit 2). 매뉴얼과 코드 어긋남 감시.

### PostToolUse (사후 검증)
- **code_reviewer** — 코드 수정 직후 다층 리뷰.
- **verify_guard** — 코드 수정 직후 타입체크·린트 실행 (`.claude/verify.json` 또는 자동감지).

### SessionStart (세션 시작)
- **codemap_session** — `docs/codemap.md`를 자동 로드해 에이전트가 코드 구조를 즉시 파악.

### Stop (작업 종료)
- **backpressure** — 자기 검증.
- **report_generator** — `.claude/reports/latest.html` 생성.
- **codemap_refresh** — 코드가 바뀌었으면 코드맵 자동 갱신(다음 세션 대비).

### 모니터링 보조 (활성화 시에만 동작)
- **monitor**, **monitor_report** — 훅 동작 로그·요약.

## 도메인 설계 사이클

이번 하네스의 가장 큰 추가. AI 코딩의 흔한 실패("설계 모순을 안고 코드부터 짜기 시작 → 나중에 발견 → 큰 폭 재작업")를 막기 위한 흐름.

```
새 도메인 시작
    │
    ▼ "도메인 설계 시작"  ────► domain-interview
    │                          ├─ Phase 0: 도메인 발견 (intent, domain_map, boundaries)
    │                          └─ Phase 1: 슬롯 채우기 (data_model, api_contract, error_handling, edge_cases)
    │                          → docs/domains/<domain>/interview.json (모순 검출, 결정 기록)
    │
    ▼ 인터뷰 complete       ────► domain-manual
    │                          → docs/domains/<domain>/manual.md (불변 규칙·의존 계약·핵심 모델)
    │                          → docs/domains/README.md (도메인 지도)
    │
    ▼ 구현 시작
    │
    ▼ 코드 수정             ────► drift_guard (PreToolUse) 자동 발동
                              ├─ interview_status != complete → 차단(exit 2)
                              └─ 코드가 매뉴얼 동기화 시점 이후 변경 → 경고(통과)

              + domain-refactor 스킬로 사후 진단 가능(매뉴얼 기준 위반 리포트)
```

핵심: **인터뷰→매뉴얼이 디스크의 파일**이라 모델 중립적이고, 다음 세션·다른 도구로도 그대로 이어진다.
바로 이 점이 Codex 분업(아래 design-harness)으로 확장 가능한 이유.

## 검증 레이어 (verify_guard)

코드 수정 직후 PostToolUse 훅이 자동 실행. 빠른 피드백.

설정 우선순위:
1. `.claude/verify.json`이 있으면 그 명령을 사용 (lint/typecheck/test).
2. 없으면 프로젝트 마커로 자동 감지(pyproject.toml→pytest, package.json→npm test/lint, Cargo.toml→cargo).

기본 정책: **실패해도 차단 안 함, 경고만**. 작업 중간엔 테스트가 깨질 수 있어서.
자동감지 시엔 test 기본 생략(노이즈 방지), verify.json에 명시할 때만 test도 실행.

예시 `verify.example.json`이 각 템플릿 `.claude/`에 포함.

## 코드맵 (세션 연속성)

`docs/codemap.md`는 각 파일이 무엇을 export하고 어떤 로컬 모듈을 import하는지의 정적 파싱 결과.
세션이 끊겨도 다음 세션이 전체 코드를 다 읽지 않고 구조를 빠르게 파악하기 위한 것.

- **SessionStart 시 자동 로드** (codemap_session 훅).
- **Stop 시 자동 갱신** (codemap_refresh 훅, 소스가 코드맵보다 최신일 때만).
- 수동 갱신: `python3 .claude/hooks/codemap.py`
- 지원: Python(AST), JS/TS(정규식 근사).
- 직접 수정 금지 — 자동 생성물.

## 모니터링 (활성화 시에만)

하네스 훅이 실제로 발동했는지 확인하는 도구. 평소엔 꺼두고 검증 운행 시 켠다.

```bash
export HARNESS_MONITOR=1   # 켜기
# ... 하네스 사용 ...
/monitor                   # 요약 보기
unset HARNESS_MONITOR      # 끄기
```

`.claude/monitor.log`에 JSON Lines로 쌓이고 (`{ts, hook, target, result}`),
`/monitor`(또는 `python3 .claude/hooks/monitor_report.py`)로 훅별 발동 횟수·차단/실패 이벤트 요약을 본다.

대상 훅: drift_guard, verify_guard, codemap_session, codemap_refresh.
환경변수 안 켜면 오버헤드 0 (로그 파일도 안 생김).

## 모델 분배 (Claude Code 에이전트별)

성격에 맞는 모델을 박아 비용·품질을 right-sizing:
- **설계** → `claude-opus-4-7` (architect, ui-planner)
- **구현** → `claude-sonnet-4-6` (backend-dev, frontend-dev, ui-designer, error-handler, automation-dev, browser-dev, integration-dev)
- **QA·검증** → `claude-haiku-4-5-20251001` (code-verifier, qa-engineer, qa-tester, error-curator)

opus-4-7은 Claude Code v2.1.111+ 필요. 미만 버전이면 `claude update`로 업그레이드.

## 실행 가이드

### Step 1: 프로젝트 생성

```bash
cd jarvis-harness-kit
bash scaffold.sh <프로젝트명> [도메인]

# 예시
bash scaffold.sh my-saas webapp        # 일반 웹앱
bash scaffold.sh my-bot automation     # → browser-dev, automation-dev, browser-automation 스킬 자동 활성화
bash scaffold.sh video-factory youtube # → 위 + integration-dev
bash scaffold.sh jarvis-clone agent    # → integration-dev + automation-dev + task-routing 스킬
bash scaffold.sh my-api api            # backend 위주
```

대화형 프롬프트로 템플릿(범용/챗봇), DB, 모니터링, 로컬 LLM을 선택.

### Step 2: 첫 명령

```bash
cd <프로젝트명>
claude

# 새 도메인 설계부터
> 도메인 설계 시작

# 또는 기존 흐름
> /plan-start      # 기획부터
> /architect       # PRD 있으면 스캐폴딩 직행
> /dev-start       # 자유 개발
```

세션 시작 시 자동으로 — CLAUDE.md(전역 코딩 규칙)가 로드되고, `docs/codemap.md`가 있으면 코드 구조가 컨텍스트에 깔린다.
코드 수정 시 — drift_guard(PreToolUse)가 매뉴얼 어긋남을 차단·경고하고, verify_guard(PostToolUse)가 타입체크·린트를 즉시 돌린다.

## 풀 사이클 워크플로우

```
[도메인 발견·설계 사이클]
goal.md / prd.md                       (옵션) 사용자 요청
       │                                       │
       ▼                                       ▼
  ui-planner ──► docs/spec.md          domain-interview ──► interview.json
                                                            ▼
                                                       domain-manual ──► manual.md (+도메인 지도)
                                                            │
                                                            └─► drift_guard가 이후 코드 수정을 감시
[구현·검증]
spec.md
   │
   ▼
architect (스캐폴딩, opus-4-7)
   │
   ├─► ui-designer (ui-spec.md, sonnet-4-6)
   ├─► qa-tester (test-cases.md, haiku)
   │
   ▼
backend-dev / frontend-dev (병렬, sonnet-4-6)
   │  (도메인 따라 browser-dev / integration-dev / automation-dev 추가)
   │
   ▼ 모듈 단위 완료
verify_guard (자동, PostToolUse) — 타입체크·린트
code-verifier (haiku) — 다층 검증
qa-engineer (haiku) — 모듈 경계 비교
   │
   ▼ 작업 종료 (Stop 훅)
codemap_refresh — 코드맵 박제
report_generator — verification-report 생성
(오류 발생 시) error-curator → lessons-learned.md
```

각 에이전트는 `_workspace/{NN}_{agent}_report.md`에 보고서를 남겨 부분 재실행/이어하기 가능.

## 검증 대시보드

세션 종료 시 `.claude/reports/latest.html`이 자동 생성.

```bash
open .claude/reports/latest.html
```

## 관련 패키지

### design-harness (별도 저장소)
Claude는 설계(인터뷰→매뉴얼→AGENTS.md export)만, **구현은 Codex CLI**가 담당하는 분업 하네스.
Claude는 코드를 직접 짜지 않고, 매뉴얼을 Codex가 읽는 `AGENTS.override.md`로 내보내 각 `code_paths`에 배치.
drift_guard·domain-refactor는 그대로 두어 사후 검출 안전망 유지.
독립 저장소로 운영.

### jarvis-harness-plugin
이 하네스 셋을 슬래시 커맨드로 설치하는 Claude Code 플러그인.

```
/plugin marketplace add <repo-url>
/plugin install jarvis-harness
/harness-init                  # 변종 선택 메뉴
/harness-init universal        # 범용 하네스 설치
/harness-init chatbot          # 챗봇 하네스 설치
/harness-init design-codex     # Codex 분업 하네스 설치
/harness-init help             # 도움말
```

잘못된 인자엔 도움말, 인자 없으면 메뉴. scaffold.sh의 복사 철학을 살리되 배포는 플러그인 표준.

## 새 프로젝트 만들기

`template/`과 `template-universal/`은 원본으로 보존. 같은 하네스로 여러 프로젝트 생성 가능:

```bash
bash scaffold.sh video-factory youtube       # YouTube 자동 업로드 봇
bash scaffold.sh my-saas webapp              # 일반 SaaS
bash scaffold.sh data-pipeline automation    # 자동화/배치
bash scaffold.sh side-project general        # 범용
```

## 한계와 알려진 사항

- 실제 Claude Code 환경에서 모든 훅 발동·환경변수 전달·플러그인 동작은 **운영 중 확인 필요**. 스크립트 로직 자체는 시나리오별로 검증했으나 통합 운영은 케이스마다 다를 수 있음.
- 코드맵 자동감지는 Python/Node/Rust만 커버. Go/Java 등은 `verify.json`으로 명시.
- 모니터링은 우리가 추가한 4개 훅만 대상(원본 훅 4개는 미적용).

## 로드맵

- [ ] **`--preset` 플래그** — `--preset=family-chatbot|saas|cli` 같은 도메인 프리셋 자동 주입.
- [ ] **examples 확장** — saas, e-commerce, data-pipeline 도메인 예제.
- [ ] **다층 피드백 계층** — PostToolUse 훅에 더해 pre-commit / CI 연동.
- [ ] **observability 확장** — Logfire/OTel 등 외부 관측가능성 도구 연동.
- [ ] **Codex 훅 이식** — Codex CLI의 apply_patch 훅 커버리지가 개선되면 drift_guard를 `.codex/hooks/`로 이식해 분업 환경에서도 실시간 차단.
