# JARVIS Harness Kit

Claude Code 하네스 모음. 도메인 설계부터 구현·검증·세션 연속성까지 한 패키지로 묶었다.
"AI가 코딩하다 폭주하는 것"을 프롬프트가 아니라 **메커니즘(훅·스킬·계약 문서)으로 강제**하는 게 핵심.

## 한눈에

- **두 프로파일** — `lite`(기본, 상시 훅 최소화) / `full`(풀 사이클 전체 구성). `bash .claude/profiles/switch.sh <lite|full>`로 전환.
- **두 템플릿** — `template-universal`(범용) / `template`(JARVIS 브라우저 챗봇 특화).
  `scaffold.sh`로 현재 프로젝트에 깔거나, `jarvis-harness-plugin`으로 슬래시 커맨드 한 줄(`/harness-init`)로 설치.
- **도메인 설계 사이클** — 인터뷰로 모순 잡고, 매뉴얼로 규칙 박고, 코드가 규칙을 어기면 훅이 차단·경고.
  `harness.config.json`으로 차단/경고/비활성 3단계 + 경로별 완화(예: `frontend/**`는 경고만) 제어.
- **검증 레이어** — 코드 수정 후 자동으로 타입체크·린트 실행(verify_guard). 코드 리뷰는 온디맨드 `/verify`.
- **코드맵** — 세션이 끊겨도 다음 세션이 코드 구조를 즉시 파악(SessionStart 자동 로드, Stop 시 자동 갱신).
- **모니터링** — `HARNESS_MONITOR=1` 켜면 어떤 훅이 몇 번 발동했는지 기록, `/monitor`(full)로 요약.
- **모델 분배** — 설계=opus-4-7 / 구현=sonnet-4-6 / QA=haiku-4-5. 에이전트별로 박혀 있음.
- **관련 패키지** — `design-harness`(Claude 설계 + Codex 구현 분업) 별도 저장소.

## 프로파일 (lite / full)

훅이 매 수정마다 3연발(PreToolUse 1 + PostToolUse 2)로 발동하면 체감 지연과 토큰 비용이 크다.
그래서 킷을 두 프로파일로 나눴다. **기본값은 lite.**

| | **lite (기본)** | **full** |
|---|---|---|
| 상시 훅 | security_gate, drift_guard(완화 모드), secret_scan, verify_guard, codemap 2종 | 좌측 + code_reviewer(PostToolUse), backpressure(Stop), report_generator(Stop) |
| 코드 리뷰 | 온디맨드 — `/verify` (Layer D로 흡수) | 매 수정마다 자동 (code_reviewer 훅) |
| 커맨드 | `/verify`, `/code-review`, `/security-review`, `/dev-start`, `/lessons` | + 설계/구현/검증 풀 사이클 커맨드 전체 |
| 에이전트 | code-verifier, error-curator, security-reviewer | + ui-planner, architect, dev 페어, qa 페어 등 8개 |
| 스킬 | domain-interview / manual / refactor, security-review, code-walkthrough | + grill, tdd, diagnose, architecture, orchestrator (챗봇 템플릿은 특화 스킬 추가) |
| 용도 | 일상 개발 (도메인 사이클 + 최소 안전망) | 검증 운행, 배포 전 점검, 풀 사이클 신규 구축 |

전환:

```bash
bash .claude/profiles/switch.sh full   # 전체 구성 활성화
bash .claude/profiles/switch.sh lite   # 최소 구성으로 복귀
```

훅 스크립트는 어느 프로파일에서도 삭제되지 않는다(`settings.json` 등록 여부로만 제어) — 전환은 항상 가역적.
현재 프로파일은 `harness.config.json`의 `profile` 필드에 기록된다.

## harness.config.json (drift_guard 완화)

프로젝트 루트의 설정 파일 하나로 drift_guard의 강도를 제어한다:

```json
{
  "profile": "lite",
  "drift_guard": {
    "mode": "block",
    "warn_paths": ["frontend/**"]
  }
}
```

- **mode** — `block`(기본, 기존 동작) / `warn`(모든 차단을 경고로 강등) / `off`(비활성).
- **warn_paths** — `block` 모드여도 이 glob에 걸리는 경로는 차단 대신 경고만 한다.
  "만들며 설계가 잡히는" 프론트엔드 UI 반복 작업과 인터뷰 게이트가 충돌할 때 쓴다.
- **하위 호환** — 파일이 없거나 깨졌거나 mode 값이 잘못되면 **기존 동작(전체 차단)** 그대로.
  기존 설치 프로젝트는 아무것도 안 해도 동작이 바뀌지 않는다.
- 매칭은 fnmatch 기반이라 `*`가 `/`를 넘어 매칭된다(`frontend/*`도 하위 전체에 걸림). 정밀 제어가 필요하면 패턴을 좁게 쪼갤 것.
- exit 계약은 불변: 0=허용, 2=차단(사유는 stderr). 완화 경고는 stdout의 훅 JSON
  (`hookSpecificOutput.additionalContext`)으로 나가며 **모델 컨텍스트에 주입**된다 —
  에이전트가 "완화됐지만 인터뷰를 따라잡으라"는 지시를 실제로 받는다. `permissionDecision`은
  넣지 않으므로 권한 흐름에는 영향 없음.

## 템플릿 비교

| 항목 | `template-universal` (기본) | `template` (JARVIS 챗봇) |
|---|---|---|
| 에이전트 | lite 3 / full 11 + 3개 optional | 동일 |
| 스킬 | lite 5 / full 10 + optional 2개 | lite 5 / full 15 (브라우저/챗봇 도메인 5개 추가) |
| 커맨드 | lite 5 / full 15 | lite 5 / full 16 (`/browser-status` 추가) |
| 룰 | 없음 | cdp-init, ws-protocol |
| 훅 | 스크립트 12종 존치, lite 등록 6종 / full 등록 9종 (양쪽 동일) | 동일 |
| CLAUDE.md | `{{PROJECT_NAME}}` 슬롯, 도메인 비종속 | JARVIS 도메인 박힘 |

full 전용 자산은 각 템플릿의 `.claude/profiles/full/{commands,agents,skills}/`에 있고, `switch.sh full`이 루트로 복사한다.

## 에이전트 (11개 기본 + 3개 optional)

lite 프로파일에서는 **code-verifier, error-curator, security-reviewer**만 활성. 나머지는 `.claude/profiles/full/agents/`에 있다가 `switch.sh full`로 활성화.

### 기본 (full 기준, `.claude/agents/`)
- **architect** (opus-4-7) — 빌드 골격·도메인 엔티티·공유 타입 스캐폴딩.
- **ui-planner** (opus-4-7) — 요구사항·스펙·화면 ID 정의.
- **security-reviewer** (opus-4-7) — 논리적 취약점(권한 검증 누락, IDOR, RLS 구멍) 전담. 읽기 전용, `/security-review`로 호출.
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

lite 프로파일에는 도메인 설계 사이클 3종 + security-review + code-walkthrough만 포함. 나머지는 full 전용.

### 보안 (lite/full 공통)
- **security-review** — 스택 특화 보안 지식 문서(Supabase RLS, Next.js Server Action, FastAPI) + 논리 취약점 방법론(권한 매트릭스, IDOR). security-reviewer 에이전트가 사용.

### 코드 이해 (lite/full 공통)
- **code-walkthrough** — 코드 이해용 워크스루 방법론: 의도 순서 요약, 읽기 가이드(정거장 3~7개),
  도메인 매뉴얼 대응(매뉴얼에 없는 결정 표면화 = drift 조기 발견), 위험 지점 2~3, 이해 확인 질문 3.
  `/code-review`가 사용. 버그 찾기가 아니라 **오너의 이해 부채 상환**이 목적 — `docs/reviews/last-review.json`으로
  마지막 리뷰 시점을 추적해 "그 이후 쌓인 것"만 리뷰한다.

### 도메인 설계 사이클 (이번 하네스의 핵심 — lite/full 공통)
- **domain-interview** — 도메인 발견 → 슬롯 인터뷰 → 모순 검출. `docs/domains/<domain>/interview.json`에 결정 기록.
- **domain-manual** — 인터뷰를 매뉴얼(불변 규칙·의존 계약)로 변환. `docs/domains/<domain>/manual.md`.
- **domain-refactor** — 매뉴얼 기준으로 코드 진단(기본 report 모드). 매뉴얼에 근거 없는 변경 금지.

### 범용 워크플로우 (full 전용)
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

## 슬래시 커맨드

| 분류 | 커맨드 | 프로파일 |
|---|---|---|
| 검증·보조 | `/verify`(온디맨드 코드 리뷰 포함), `/code-review`(이해용 워크스루), `/security-review`, `/dev-start`, `/lessons` | **lite** |
| 설계·기획 | `/grill`, `/plan-start`, `/architect`, `/ui-design` | full |
| 구현·테스트 | `/tdd`, `/test-cases`, `/diagnose` | full |
| 검증·리포트 | `/qa-boundary`, `/verify-report`, `/monitor` | full |

각 커맨드 frontmatter에 description이 있어 `/` 메뉴에서 설명을 본다.
챗봇 템플릿엔 `/browser-status` (CDP 인스턴스 점검, full) 추가.

### 은퇴된 커맨드 → 공식 플러그인 대체

커머디티 워크플로우는 킷에서 유지보수하지 않고 공식 플러그인을 쓴다:

| 은퇴 커맨드 | 대체 |
|---|---|
| `/commit` | **commit-commands** 플러그인 |
| `/pr-review` | **pr-review-toolkit** 플러그인 |

```
/plugin install commit-commands
/plugin install pr-review-toolkit
```

여기에 **language server 플러그인**(사용 스택의 LSP 연동)을 병행 설치하면 verify_guard의
타입체크·린트 피드백과 별개로 편집 시점 진단이 붙어 lite 프로파일의 안전망이 두꺼워진다.

## Hooks (스크립트 12종, 양쪽 템플릿 공통 — 등록은 프로파일이 결정)

### PreToolUse (사전 차단/검사) — lite/full 공통
- **security_gate** — Bash 명령 안전 검사 (정적 regex, LLM 없음, ~0ms).
- **drift_guard** — 코드 수정 전, "미완성 도메인 코드 수정" 차단(exit 2). 매뉴얼과 코드 어긋남 감시.
  `harness.config.json`으로 완화(warn/off, warn_paths) 가능.

### PostToolUse (사후 검증)
- **secret_scan** *(lite/full)* — 전용 시크릿 유출 탐지. 내장 패턴(API 키, private key,
  **Supabase service_role JWT는 payload 디코딩으로 판별**) + gitleaks/trufflehog 설치 시 추가 스캔.
  탐지 시 차단(exit 2)하고 환경변수 이전·키 로테이션을 안내. LLM 없이 항상 동작.
- **verify_guard** *(lite/full)* — 코드 수정 직후 타입체크·린트 실행 (`.claude/verify.json` 또는 자동감지).
- **code_reviewer** *(full 전용)* — 코드 수정 직후 자동 다층 리뷰(LLM 호출).
  lite에서는 자동 발동하지 않으며 `/verify`의 Layer D로 온디맨드 실행 — 매 수정 지연·토큰 비용의 주범이었다.

### SessionStart (세션 시작) — lite/full 공통
- **codemap_session** — `docs/codemap.md`를 자동 로드해 에이전트가 코드 구조를 즉시 파악.

### Stop (작업 종료)
- **codemap_refresh** *(lite/full)* — 코드가 바뀌었으면 코드맵 자동 갱신(다음 세션 대비).
- **backpressure** *(full 전용)* — 자기 검증 (타입체크/린트/테스트, 실패 시 exit 2 재작업 강제).
- **report_generator** *(full 전용)* — `.claude/reports/latest.html` 생성.

### 모니터링 보조 (활성화 시에만 동작)
- **monitor**, **monitor_report** — 훅 동작 로그·요약 (`HARNESS_MONITOR=1`일 때만, 평시 오버헤드 0).

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
                              │    (단, harness.config.json의 mode=warn 또는 warn_paths 매칭 시 경고로 강등)
                              └─ 코드가 매뉴얼 동기화 시점 이후 변경 → 경고(통과)

              + domain-refactor 스킬로 사후 진단 가능(매뉴얼 기준 위반 리포트)
```

핵심: **인터뷰→매뉴얼이 디스크의 파일**이라 모델 중립적이고, 다음 세션·다른 도구로도 그대로 이어진다.
바로 이 점이 Codex 분업(아래 design-harness)으로 확장 가능한 이유.

## 보안 레이어 (3층)

역할이 다른 세 층이 각각 다른 종류의 결함을 잡는다. 전부 lite 포함:

| 층 | 대상 | 방식 | 발동 |
|---|---|---|---|
| **security_gate** (훅) | 위험 bash 명령 (rm -rf /, 원격 스크립트 파이프 등) | 정적 regex, ~0ms | PreToolUse 자동 |
| **secret_scan** (훅) | 시크릿 유출 — API 키, private key, **Supabase service_role JWT**(payload 디코딩 판별) | 내장 패턴 + gitleaks/trufflehog(설치 시) | PostToolUse 자동, 탐지 시 차단 |
| **security-reviewer** (에이전트) + security-review (스킬) | 논리 취약점 — 권한 검증 누락, IDOR, RLS 구멍, mass assignment | opus 에이전트가 권한 매트릭스·스택 체크리스트(Supabase RLS, Next.js Server Action, FastAPI)로 진단 | `/security-review` 온디맨드 |

gitleaks/trufflehog는 **선택적** — 설치돼 있으면 secret_scan이 자동으로 추가 활용하고, 없어도 내장 패턴만으로 동작한다(의존성 강제 없음). `brew install gitleaks` 권장.

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
- **설계·보안** → `claude-opus-4-7` (architect, ui-planner, security-reviewer)
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

대화형 프롬프트로 템플릿(범용/챗봇), DB, 모니터링, 로컬 LLM, **하네스 프로파일(기본 lite)**을 선택.
full을 선택하면 복사 직후 `switch.sh full`이 자동 실행된다.

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

## 풀 사이클 워크플로우 (full 프로파일)

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

## 검증 대시보드 (full 프로파일)

full 프로파일에서 세션 종료 시 `.claude/reports/latest.html`이 자동 생성 (report_generator 훅).

```bash
open .claude/reports/latest.html
```

## 기존 설치 프로젝트 마이그레이션

이미 이 킷으로 운영 중인 프로젝트(예: 은하계 인맥 커뮤니티 — FastAPI + Next.js + Supabase, 멀티 도메인)를
lite 프로파일로 옮기는 절차. **도메인 매뉴얼 파일 포맷과 codemap 산출물 포맷은 바뀌지 않았으므로**
`docs/domains/`, `docs/codemap.md`는 그대로 두면 된다.

### 절차 (킷 → 운영 프로젝트 반영)

1. **훅 스크립트 교체** — 킷의 `template-universal/.claude/hooks/drift_guard.py`를 프로젝트 `.claude/hooks/`에 복사.
   (다른 훅 스크립트는 변경 없음. 전부 복사해도 무해.)
2. **프로파일 구조 복사** — 킷의 `template-universal/.claude/profiles/` 디렉토리를 프로젝트 `.claude/`에 복사.
3. **커스텀 확인 후 settings.json 교체** — 프로젝트 `settings.json`에 직접 추가한 훅/권한이 있으면 백업.
   `bash .claude/profiles/switch.sh lite` 실행(= lite settings 적용 + full 전용 커맨드/에이전트/스킬을 루트에서 제거).
4. **harness.config.json 생성** — 프로젝트 루트에:
   ```json
   { "profile": "lite", "drift_guard": { "mode": "block", "warn_paths": ["frontend/**"] } }
   ```
   frontend 디렉토리 이름이 다르면 glob을 맞출 것. 이 파일을 만들지 않으면 drift_guard는 기존처럼 전체 차단.
5. **은퇴 커맨드 제거·대체** — `.claude/commands/commit.md`, `pr-review.md` 삭제 후
   `/plugin install commit-commands`, `/plugin install pr-review-toolkit` (+ 스택에 맞는 language server 플러그인 권장).
6. **CLAUDE.md 갱신** — 킷 템플릿의 "하네스 프로파일" 섹션을 이식하고, 커맨드 목록에서 `/commit`·`/pr-review`를 지운다.

### 은하계 커뮤니티 프로젝트 체크리스트

- [ ] `.claude/hooks/drift_guard.py` 교체 (완화 모드 지원 버전)
- [ ] `.claude/profiles/` 복사 + `switch.sh lite` 실행
- [ ] `harness.config.json` 생성 — `warn_paths`에 실제 프론트엔드 경로(glob) 지정
- [ ] 도메인별 확인: 인터뷰 complete인 도메인은 동작 변화 없음 / 진행 중 도메인의 backend 수정은 여전히 차단되는지 1회 확인
- [ ] frontend 파일 수정 시 차단 대신 `[drift-guard]…완화 모드` 경고가 뜨는지 1회 확인
- [ ] `/verify` 실행해 code-verifier(Layer D 코드 리뷰 포함) 정상 동작 확인 — 매 수정 자동 리뷰는 더 이상 없음
- [ ] `/commit`·`/pr-review` 삭제, 공식 플러그인 설치
- [ ] 보안 레이어 이식: `secret_scan.py` 훅 복사 + settings 등록, `security-reviewer` 에이전트·`security-review` 스킬·커맨드 복사. (선택) `brew install gitleaks`
- [ ] Supabase service_role 키가 프론트 코드·`NEXT_PUBLIC_*`에 없는지 `/security-review`로 1회 전수 점검
- [ ] 이전 대비 체감: 코드 수정 시 PostToolUse가 secret_scan(~ms)+verify_guard만 도는지 (지연 감소 확인)
- [ ] 배포 전 점검이나 검증 운행 때만 `switch.sh full` → 끝나면 `switch.sh lite` 복귀

### 회귀 테스트

킷 저장소에서 훅 계약(exit 0/2, 프로파일 구성)을 검증하는 테스트를 제공:

```bash
bash tests/run_all.sh   # 23개 테스트, 표준 라이브러리만 사용
```

훅 직접 호출·`claude -p` 재현 절차는 `tests/README.md` 참조.

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

- 실제 Claude Code 환경에서 모든 훅 발동·환경변수 전달·플러그인 동작은 **운영 중 확인 필요**. 훅 스크립트 로직은 `tests/`의 회귀 테스트로 검증하지만 통합 운영은 케이스마다 다를 수 있음.
- 코드맵 자동감지는 Python/Node/Rust만 커버. Go/Java 등은 `verify.json`으로 명시.
- 모니터링은 우리가 추가한 4개 훅만 대상(원본 훅 4개는 미적용).
- `warn_paths` 매칭은 fnmatch 기반 — `*`가 경로 구분자(`/`)를 넘어 매칭되므로 `frontend/*`와 `frontend/**`가 사실상 동일하게 동작.
- 킷 저장소 안에서 `switch.sh`를 직접 실행하면 템플릿 원본이 dirty해진다. 스캐폴딩된 프로젝트에서만 사용할 것 (원상복구는 `git checkout`).

## 로드맵

- [ ] **`--preset` 플래그** — `--preset=family-chatbot|saas|cli` 같은 도메인 프리셋 자동 주입.
- [ ] **examples 확장** — saas, e-commerce, data-pipeline 도메인 예제.
- [ ] **다층 피드백 계층** — PostToolUse 훅에 더해 pre-commit / CI 연동.
- [ ] **observability 확장** — Logfire/OTel 등 외부 관측가능성 도구 연동.
- [ ] **Codex 훅 이식** — Codex CLI의 apply_patch 훅 커버리지가 개선되면 drift_guard를 `.codex/hooks/`로 이식해 분업 환경에서도 실시간 차단.
