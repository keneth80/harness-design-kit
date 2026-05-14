# JARVIS Harness Kit

Claude Code 하네스 엔지니어링이 적용된 프로젝트 템플릿 킷.
`scaffold.sh`를 실행하면 완성된 하네스(에이전트 팀 + 스킬 + 검증 Hook + 슬래시 커맨드)가 포함된 프로젝트를 생성합니다.

---

## 킷 구조

```
jarvis-harness-kit/
├── scaffold.sh            ← 프로젝트 생성기 (대화형)
├── setup-claude-optimization.sh  ← 토큰 최적화 환경 설정
├── README.md              ← 이 파일
├── GUIDE.md               ← 상세 가이드 (검증 파이프라인, 결정 트리, 커스터마이징)
├── template-universal/    ← 범용 슬롯 템플릿 (기본 선택지)
├── template/              ← JARVIS 브라우저 챗봇 도메인 템플릿
└── examples/
    └── family-chatbot/    ← 가족 챗봇 보조 자료 (commands/rules/skills 일부)
```

`scaffold.sh`는 실행 시 두 템플릿 중 하나를 선택하게 합니다 — 기본값은 `[1] 범용`. JARVIS 도메인(가족 챗봇·CDP·WebSocket·LangGraph 등) 특화 자료가 필요하면 `[2]`.

---

## 템플릿 비교

| 항목 | `template-universal` (기본) | `template` (JARVIS) |
|---|---|---|
| CLAUDE.md | `{{PROJECT_NAME}}` 슬롯, 도메인 비종속 | JARVIS 도메인 박힘 |
| 에이전트 | 9 + optional 3 | 9 + optional 3 (동일) |
| 스킬 | architecture, diagnose, grill, tdd, karpathy-guidelines | 위 + browser-automation, chatbot-ui, design-system, error-recovery, orchestrator, task-routing |
| 커맨드 | 14개 (도메인 비종속) | 15개 (`/browser-status` 추가) |
| 룰 | 없음 | cdp-init, ws-protocol |
| Hooks | security_gate, code_reviewer, backpressure, report_generator | 동일 |

---

## 에이전트 (9개 기본 + 3개 optional)

### 기본 (`.claude/agents/` 직접 자식)
| 에이전트 | 역할 | 모델 |
|---|---|---|
| ui-planner | goal.md/prd.md → spec.md | sonnet |
| architect | 빌드 설정 + 도메인 엔티티 + 공유 타입 스캐폴딩 | sonnet |
| ui-designer | UI 와이어프레임 + ui-spec.md | sonnet |
| backend-dev | 백엔드 구현 | inherit |
| frontend-dev | 프론트엔드 구현 | inherit |
| qa-tester | test-cases.md + 테스트 코드 작성 | haiku |
| qa-engineer | 컴포넌트 boundary 검증 (progressive) | haiku |
| code-verifier | Layer A~D 다층 검증 (정적/테스트/spec/lessons) | haiku |
| error-curator | error-log.md → lessons-learned.md 큐레이션 | haiku |
| error-handler | 런타임 오류 진단·복구 | haiku |

### Optional (`.claude/agents/optional/` — 도메인에 따라 자동 활성화)
| 에이전트 | 도메인 | 역할 |
|---|---|---|
| browser-dev | automation, youtube | Browser Use, Playwright, CDP, DOM 조작 |
| integration-dev | video, youtube, agent | 외부 API 클라이언트 (ElevenLabs, OpenAI, Google API 등) |
| automation-dev | automation, video, youtube, agent | LangGraph, state machine, 워크플로우 오케스트레이션 |

scaffold.sh는 사용자가 입력한 `[도메인]` 인자를 보고 위 매핑대로 optional/X.md → ../X.md 로 자동 이동시켜 활성화합니다. 매핑이 없는 도메인은 optional/에 그대로 두고 필요 시 수동 이동.

---

## 슬래시 커맨드 (14개, 도메인 비종속)

### 풀 사이클 워크플로우
| 커맨드 | 설명 | 호출 에이전트 |
|---|---|---|
| `/plan-start` | 기획 시작 (goal.md/prd.md 자동 분기) | ui-planner |
| `/architect` | 빌드 설정 + 도메인 엔티티 스캐폴딩 | architect |
| `/ui-design` | UI 와이어프레임 + ui-spec.md | ui-designer |
| `/test-cases` | 테스트 케이스 명세 + 테스트 코드 | qa-tester |
| `/qa-boundary` | 모듈 사이 boundary 검증 (progressive) | qa-engineer |
| `/verify` | Layer A~D 다층 검증 리포트 생성 | code-verifier |
| `/lessons` | error-log.md → lessons-learned.md 큐레이션 | error-curator |
| `/verify-report` | 최신 검증 대시보드 요약 | (파일 읽기) |

### 개발 보조
| 커맨드 | 설명 | 호출 스킬 |
|---|---|---|
| `/grill` | 요구사항 정렬 (구현 전 ambiguity 제거) | grill |
| `/tdd` | TDD 워크플로우 (vertical slice) | tdd |
| `/diagnose` | 시스템·오류 진단 | diagnose |
| `/commit` | 변경 요약 + Conventional Commits | (없음) |
| `/pr-review` | PR 리뷰 가이드 | (없음) |
| `/dev-start` | 프로젝트 현황 분석 + 다음 작업 제안 | (없음) |

template 쪽에는 추가로 `/browser-status` (Chrome 인스턴스 + LM Studio 상태)가 있습니다.

---

## 스킬

- **karpathy-guidelines** — LLM 코딩 4원칙(Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution). 코드 작성·리뷰 시 자동 호출, dev/code-verifier 품질 보강. (출처: multica-ai/andrej-karpathy-skills, MIT)
- **grill** — 요구사항 정렬 워크플로우
- **tdd** — vertical slice TDD
- **diagnose** — 시스템 진단
- **architecture** — 아키텍처 개선 워크플로우
- (template 전용) **design-system, error-recovery, orchestrator, task-routing, browser-automation, chatbot-ui**

---

## Hooks (4종, 양쪽 템플릿 공통)

| Hook | 이벤트 | 역할 |
|---|---|---|
| security_gate.py | PreToolUse (Bash) | 위험 명령(`rm -rf /`, DB DROP 등) 차단 |
| code_reviewer.py | PostToolUse (Write/Edit/MultiEdit) | 정적 분석 + AI 코드 리뷰 (LM Studio/Ollama) |
| backpressure.py | Stop | 타입체크/린트/테스트 실행, 실패 시 에이전트 재작업 강제 |
| report_generator.py | Stop (async) | 세션 종료 시 HTML 대시보드 생성 |

---

## 실행 가이드

### Step 1: 프로젝트 생성

```bash
cd jarvis-harness-kit
bash scaffold.sh <프로젝트명> [도메인]

# 예시
bash scaffold.sh my-saas webapp                 # 일반 웹앱
bash scaffold.sh my-bot automation              # → browser-dev, automation-dev 자동 활성화
bash scaffold.sh video-factory youtube          # → browser-dev + integration-dev + automation-dev 모두
bash scaffold.sh jarvis-clone agent             # → integration-dev + automation-dev
bash scaffold.sh my-api api                     # backend 위주
```

대화형 프롬프트:

| 항목 | 선택지 | 기본값 |
|------|--------|--------|
| 0️⃣ 템플릿 | 범용(universal), JARVIS | 1: 범용 |
| 1️⃣ DB | Supabase 로컬, Supabase 클라우드, PostgreSQL, SQLite, 없음 | 5: 없음 |
| 2️⃣ 모니터링 | agents-observe, Hook 로깅, 없음 | 2: Hook 로깅 |
| 3️⃣ 로컬 LLM | LM Studio, Ollama, 없음 | 1: LM Studio |

### Step 2: 첫 명령

```bash
cd <프로젝트명>
claude

# 기획부터
> /plan-start

# 또는 PRD가 이미 있으면 스캐폴딩으로 직행
> /architect

# 자유 개발
> /dev-start
```

CLAUDE.md가 자동으로 로드되어 프로젝트 컨텍스트(아키텍처, 기술 스택, 코딩 규칙)를 파악합니다. 코드를 작성·수정하기 직전마다 **karpathy-guidelines** 스킬이 자동 호출되어 4원칙 자가 점검을 강제합니다.

---

## 풀 사이클 워크플로우

```
goal.md 또는 prd.md
       │
       ▼
ui-planner ─────► docs/spec.md
                       │
            ┌──────────┼──────────┐
            ▼          ▼          ▼
       architect   ui-designer  qa-tester
       (스캐폴딩)  (ui-spec.md) (test-cases.md)
            │          │          │
            └──────────┼──────────┘
                       ▼
       ┌──── backend-dev / frontend-dev (병렬) ────┐
       │ (도메인에 따라 browser-dev /                 │
       │  integration-dev / automation-dev 추가)      │
       │                                              │
       │ 모듈 하나 완료 시마다 ↓                       │
       │                                              │
       │   code-verifier (자동) — Layer A/B/C/D       │
       │   qa-engineer  (수동) — boundary 비교         │
       └──────────────────────────────────────────────┘
                       │
                       ▼
              docs/verification-report.md
              _workspace/04_qa_engineer_report.md
              (오류 발생 시) error-curator → lessons-learned.md
```

각 에이전트는 `_workspace/{NN}_{agent}_report.md`에 보고서를 남기므로 부분 재실행/이어하기 가능.

---

## 검증 대시보드

세션 종료 시 `.claude/reports/latest.html`에 자동 생성됩니다.

```bash
open .claude/reports/latest.html
```

---

## 새 프로젝트 만들기

`template/`과 `template-universal/`은 원본으로 보존됩니다. 같은 하네스 기반으로 여러 프로젝트 생성 가능:

```bash
bash scaffold.sh video-factory youtube       # YouTube 자동 업로드 봇
bash scaffold.sh my-saas webapp              # 일반 SaaS
bash scaffold.sh data-pipeline automation    # 자동화/배치
bash scaffold.sh side-project general        # 범용
```

---

## 로드맵

- [ ] **settings.json 플러그인화** — Python Hook 4개를 `harness@harness-marketplace` 플러그인으로 패키징하여 settings.json 슬림화 + 일관 업데이트.
- [ ] **`--preset` 플래그** — `--preset=family-chatbot|saas|cli` 같은 도메인 프리셋 자동 주입.
- [ ] **examples 확장** — saas, e-commerce, data-pipeline 등 도메인 예제.
- [ ] **karpathy-guidelines 외 추가 외부 스킬 통합** — 검증된 오픈소스 SKILL을 부드럽게 흡수하는 패턴.
