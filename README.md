# Harness Design Kit v2

Claude Code용 하네스를 **플러그인 마켓플레이스**로 묶은 저장소입니다.
한 번 설치하면 모든 프로젝트에 보안 게이트가 깔리고, 필요한 프로젝트에서만 워크플로우와 에이전트 팀을 켭니다.

> v1(템플릿 복사 + scaffold.sh)에서 옮겨오는 경우 [docs/MIGRATION.md](docs/MIGRATION.md)를 먼저 보세요.

## 한눈에

| 플러그인 | 켜는 범위 | 하는 일 |
|---|---|---|
| **harness-core** | 사용자 전체 (항상) | 시크릿·외부 전송·검증기 변조를 막는 보안 게이트, 편집 후 검증, 코드맵, 도메인 설계 사이클 |
| **harness-full** | 프로젝트별 | 풀 사이클 에이전트 팀 8종, 단계 스킬, **오케스트레이션 워크플로우 3종**, 종료 전 백프레셔 |
| **harness-codex** | 프로젝트별 | Claude는 설계만, 구현은 Codex CLI. 코드 쓰기 차단 + AGENTS.override.md 내보내기 |
| **harness-automation** | 프로젝트별 | 브라우저 자동화·외부 API 연동·장시간 워크플로우 전문 에이전트 3종 |
| **harness-design** | 프로젝트별 | 디자인 브리프·토큰·design_guard·4종 스크린샷 측정·design-critic 채점, 시안 경쟁 워크플로우 |

비유하면 harness-core는 몸에 차는 **공구벨트**(어느 현장에 가든 따라옴), 나머지는 현장에 가져가는 **장비 상자**입니다.
그 현장에서만 의미 있는 규칙(예: 특정 서비스의 셀렉터)은 그 프로젝트의 `.claude/`에 둡니다.

## 설치

```bash
# 1) 마켓플레이스 등록 (한 번)
claude plugin marketplace add keneth80/harness-design-kit

# 2) core는 사용자 범위로 → 모든 프로젝트에 적용
claude plugin install harness-core@harness-design-kit

# 3) 나머지는 설치만 해두고 (기본 꺼짐)
claude plugin install harness-full@harness-design-kit
claude plugin install harness-codex@harness-design-kit
claude plugin install harness-automation@harness-design-kit
claude plugin install harness-design@harness-design-kit
claude plugin install frontend-design@claude-plugins-official   # harness-design과 함께 쓰는 공식 디자인 스킬
```

Claude Code 세션 안에서는 `/plugin`으로 같은 일을 할 수 있습니다. 터미널, 데스크톱 앱, VS Code, Orca처럼 `~/.claude`를 읽는 도구는 같은 설치를 공유합니다.

## 프로젝트에서 쓰기

```bash
cd my-project

# 워크플로우 켜기 (편집 후 검증, 코드맵, 드리프트 가드)
claude                       # 세션에서 /harness-core:init

# 이 프로젝트에서만 풀 사이클 팀 켜기
claude plugin enable harness-full@harness-design-kit --scope local

# 또는 이 프로젝트를 설계 전용(Codex 구현)으로
claude plugin enable harness-codex@harness-design-kit --scope local
```

`--scope local`은 `.claude/settings.local.json`(gitignore 대상)에 기록되므로 팀원에게 영향을 주지 않습니다. 팀 전체에 켜려면 `--scope project`.

### 프로젝트마다 init하기도 귀찮다면

`~/.claude/harness.config.json`에 아래를 두면, 깃 저장소이고 소스 파일이 30개 이상인 프로젝트를 처음 열 때 `harness.config.json`을 자동으로 만듭니다.

```json
{ "auto_init": true, "auto_init_min_files": 30 }
```

auto_init을 켜지 않아도 보안 게이트는 이미 모든 프로젝트에서 동작합니다. 큰 저장소에서는 세션 시작 때 init을 한 줄 권합니다.

## harness-core

### 항상 동작 (init 불필요)

| 훅 | 시점 | 판정 |
|---|---|---|
| `bash_gate` | Bash 실행 전 | 명령을 토큰으로 나눠 파이프·체인 단위로 해석. 시크릿 파일 읽기(cat·head·grep·python -c·$(...) 등 모든 방법), `curl \| sh`, 광범위 삭제, 하네스 플러그인 수정은 **deny**. 외부 업로드, 강제 푸시, 설정 파일 수정, 환경변수 덤프는 **ask** |
| `file_gate` | Read·Grep·Write·Edit 전 | 시크릿 파일 읽기 deny. 코드에 API 키·개인키·토큰, 주민등록번호, 실제 카드번호(Luhn)를 **쓰기 전에** deny. 하네스 설정 수정은 ask |
| `drift_guard` | Write·Edit 전 | `docs/domains/`가 있을 때만. 인터뷰가 complete 아닌 도메인의 코드 수정 deny, 매뉴얼보다 코드·인터뷰가 새로우면 경고 |

막을 때는 이유와 대안을 같이 알려줍니다. 예: "키 이름은 .env.example에서 확인하고, 값은 사용자에게 설정을 요청하세요."

### init한 프로젝트에서만

| 훅 | 시점 | 하는 일 |
|---|---|---|
| `session_start` | 세션 시작 | 하네스 상태 한 줄 + `docs/codemap.md` 주입 |
| `verify_guard` | 편집 직후 | 린트·타입체크 실행, 실패하면 결과를 모델 컨텍스트에 넣음 (차단 안 함) |
| `codemap_refresh` | 응답 종료 | 소스가 바뀌었으면 코드맵 갱신 |

### 스킬 (`/harness-core:<이름>`)

| 스킬 | 용도 |
|---|---|
| `init` | 이 프로젝트에 워크플로우 켜기, v1 잔재 정리 |
| `verify` | code-verifier(haiku)로 4개 레이어 검증 → `docs/verification-report.md` |
| `code-review` | 오너의 이해를 위한 워크스루 (의도 순서 요약, 읽기 가이드, 이해 확인 질문) |
| `security-review` | security-reviewer(opus)로 권한 매트릭스·IDOR·RLS 점검 |
| `domain-interview` → `domain-manual` → `domain-refactor` | 도메인 설계 사이클 |
| `dev-start` | 현재 상태 파악 + 다음 작업 3개 |
| `lessons` | 학습된 교훈·오류 기록 조회 |
| `codemap` | 코드맵 지금 다시 만들기 |
| `audit` | 게이트가 무엇을 왜 막았는지 요약 |
| `harden` | Claude Code 권한 deny 규칙·샌드박스·시크릿 참조 패턴 안내 |

에이전트: `code-verifier`(haiku), `security-reviewer`(opus), `error-curator`(haiku).

### 도메인 설계 사이클

AI 코딩의 흔한 실패는 "설계 모순을 안은 채 코드부터 짜고, 나중에 발견해서 크게 갈아엎기"입니다.

```
domain-interview  →  docs/domains/<도메인>/interview.json   (슬롯 채우기 + 모순 검출, complete까지 유한 루프)
domain-manual     →  docs/domains/<도메인>/manual.md        (불변 규칙·의존 계약·결정 근거, code_paths)
drift_guard       →  code_paths의 코드는 인터뷰가 complete일 때만 수정 허용
domain-refactor   →  매뉴얼 기준으로 코드 진단 (report 모드)
```

## harness-full

켜면 에이전트 팀과 단계별 스킬이 추가되고, 응답을 끝내기 전에 백프레셔가 린트·타입체크·테스트를 돌립니다.

| 단계 | 스킬 | 에이전트 (모델) |
|---|---|---|
| 정렬 | `grill` | — |
| 기획 | `plan-start` | ui-planner (opus) |
| 골격 | `architect` | architect (opus) |
| UI | `ui-design` | ui-designer (sonnet) |
| 테스트 | `test-cases`, `tdd` | qa-tester (haiku) |
| 구현 | `full-cycle`(워크플로우), `orchestrator`(대화형) | backend-dev, frontend-dev (sonnet) |
| 경계 | `qa-boundary` | qa-engineer (haiku) |
| 문제 | `diagnose`, `error-recovery`, `architecture` | error-handler (sonnet) |

모델은 `opus`·`sonnet`·`haiku` 별칭으로 지정해서 새 모델이 나와도 파일을 고칠 필요가 없습니다.
백프레셔는 같은 세션에서 3번 연속 막아도 계속 실패하면 멈추고 사용자에게 넘깁니다. 끄려면 `"backpressure": {"enabled": false}`.

### 오케스트레이션 워크플로우

v2.0의 `orchestrator` 스킬은 Claude가 대화하면서 다음 순서를 정했습니다. 지휘자가 악보 없이 기억으로 지휘하는 셈이라, 길어지면 중간 결과가 대화창에 쌓이고 순서가 흔들립니다.
v2.1은 그 순서를 Claude Code의 [동적 워크플로우](https://code.claude.com/docs/en/workflows) 스크립트로 옮겼습니다. 계획이 코드에 있고, 중간 결과는 스크립트 변수에 남고, 멈췄다가 이어서 돌릴 수 있습니다.

| 명령 | 하는 일 |
|---|---|
| `/harness-full:full-cycle` | spec 기준으로 architect → qa-tester → 기능마다 backend·frontend 병렬 → qa-engineer 경계 검증 → HIGH 이슈 1회 수정 → code-verifier. 이미 끝난 단계는 건너뜀 |
| `/harness-full:fix-until-green` | 린트·타입체크·테스트 실패를 파일별로 나눠 고치기를 반복. 통과하거나 두 라운드 연속 진전이 없으면 멈춤. 테스트 삭제·skip·any 금지 |
| `/harness-full:domain-sweep` | 모든 도메인을 매뉴얼 기준으로 동시에 진단하고, 위반마다 독립 에이전트가 반박을 시도해 살아남은 것만 리포트 |

- 각 단계는 harness-full·harness-core의 에이전트 정의(`agentType`)로 돌아서 모델 분배(설계 opus, 구현 sonnet, 검증 haiku)가 그대로 적용됩니다.
- 하네스 훅은 워크플로우 안의 에이전트에도 똑같이 걸립니다. 에이전트를 여러 개 띄워도 보안 게이트가 그대로입니다.
- 기능은 하나씩 순서대로 만듭니다. 같은 체크아웃에서 여러 기능을 동시에 고치면 파일을 덮어쓰기 때문입니다.
- 실행 중에는 사용자 입력을 받을 수 없어서 기획(plan-start)은 워크플로우 밖에서 먼저 합니다.

### 에이전트 팀 품질 관문

[에이전트 팀](https://code.claude.com/docs/en/agent-teams)(실험 기능)을 켜고 쓰면, 팀원이 작업을 "완료"로 표시할 때 `task_gate`가 린트·타입체크를 돌려 깨져 있으면 완료를 막습니다.
혼자 쓰는 할 일 목록에는 걸리지 않습니다. 끄려면 `"task_gate": {"enabled": false}`.

## harness-codex

```
Claude (design-lead)                        Codex CLI
domain-interview → domain-manual
/harness-codex:codex-handoff  ──파일──▶  src/<도메인>/AGENTS.override.md 읽고 구현
/harness-codex:codex-review   ◀──코드──  (불변 규칙·의존 계약·공통 코딩 규칙 준수)
```

- 켜면 메인 에이전트가 `design-lead`로 바뀌고, 설계 산출물(docs/, *.md, AGENTS.override.md) 밖의 쓰기가 막힙니다.
- 내보내기는 스크립트가 합니다. 인터뷰가 complete가 아니거나 매뉴얼 §7에 미해결이 있으면 내보내지 않습니다.
- 허용 경로는 `harness.config.json`의 `"codex": {"design_paths": [...]}`로 바꿉니다.

## harness-design

AI가 만든 화면이 평범해지는 이유는 세 가지입니다. 방향이 없고, 기준이 없고, 결과를 눈으로 보지 않습니다. 눈을 감고 그림을 그리는 화가와 같습니다. harness-design은 셋을 각각 채웁니다.

| 빠진 것 | 채우는 것 |
|---|---|
| 방향 | `/harness-design:design-brief` 목적·사용자·무드·레퍼런스·금지 사항을 `docs/design/brief.md`로 고정. 공식 frontend-design 스킬과 함께 씀 |
| 기준 | `/harness-design:design-system` 브리프에서 색·타이포·간격 토큰 도출, 대비비 계산. `design_guard` 훅이 하드코딩 색·Tailwind 임의값·4px 격자 밖 값을 경고 |
| 눈 | `/harness-design:design-review` 모바일·데스크톱 × 라이트·다크 4종 스크린샷 + 명도 대비·가로 넘침·터치 영역·이름 없는 컨트롤 측정 → design-critic(opus)이 8개 항목으로 채점 → 상위 3개 수정 → 다시 찍기 (최대 3라운드) |

**`/harness-design:design-polish` 워크플로우**는 오케스트레이션과 디자인을 합친 것입니다.
서로 확실히 다른 방향의 시안 2~4개를 HTML 목업으로 만들고, 브랜드·사용성·완성도 관점의 심사위원 3명이 이름을 가린 채 채점해 1위를 고른 뒤, 비평 → 수정 → 재촬영을 반복합니다. 실제 코드는 바꾸지 않고, 적용은 사용자가 고른 뒤에 합니다.

```text
/harness-design:design-polish 예약 랜딩 첫 화면
```

- 스크린샷 측정은 Playwright를 씁니다. 없으면 `npm i -D playwright && npx playwright install chromium`.
- 데스크톱 앱에서는 Browser pane의 자동 검증(`.claude/launch.json`)도 함께 쓰면 편집할 때마다 화면을 확인합니다.
- design-polish는 에이전트를 8~13개 띄우고 심사는 opus로 돌아서, 일반 대화보다 토큰을 훨씬 많이 씁니다. 시안 2개·라운드 1회로 먼저 시험해 보세요 (`variants`, `rounds` 인자).

## harness-automation

`browser-dev`(Playwright·CDP), `integration-dev`(외부 SDK·rate limit·비용), `automation-dev`(LangGraph·체크포인트·재시작) 에이전트와
`browser-automation`, `task-routing`, `browser-status` 스킬. 특정 서비스용 규칙은 [examples/jarvis-chatbot](examples/jarvis-chatbot)처럼 프로젝트 `.claude/`에 둡니다.

## 설정: harness.config.json

프로젝트 루트에 이 파일이 있으면 그 프로젝트는 "init된" 상태입니다. 모든 항목은 선택이며, `~/.claude/harness.config.json`에 공통 기본값을 둘 수 있습니다 (프로젝트 값이 우선).

```json
{
  "version": 2,
  "drift_guard": { "mode": "block", "warn_paths": ["frontend/**"] },
  "verify": { "lint": "npm run -s lint", "typecheck": "npx tsc --noEmit", "test": "npm test", "run_on": ["*.ts", "*.tsx"] },
  "security": {
    "exfil": "ask",
    "config_edits": "ask",
    "secret_paths": [".env", ".env.*", "*.pem", "*.key", "secrets/**"],
    "allow_paths": [".env.example"]
  },
  "codemap": { "enabled": true },
  "backpressure": { "enabled": true },
  "codex": { "design_paths": ["docs/**", "*.md", "**/AGENTS.override.md"] },
  "automation": { "cdp_ports": [9222, 9223] },
  "task_gate": { "enabled": true },
  "design": {
    "tokens": ["src/styles/tokens.css"],
    "guard": "warn",
    "allow": [],
    "pages": [{ "label": "home", "url": "http://localhost:3000/" }]
  }
}
```

- `drift_guard.mode`: `block`(기본) · `warn`(차단을 경고로) · `off`. `warn_paths`는 해당 경로만 경고로.
- `verify`: 비우면 package.json 스크립트·ruff·mypy·cargo·go로 자동감지. 편집마다 테스트를 돌리려면 `"skip_test_on_edit": false`.
- `security.exfil`, `config_edits`: `ask` 또는 `deny`. `secret_paths`를 지정하면 기본 목록을 대체합니다.
- `design.tokens`가 있어야 design_guard가 켜집니다. `pages`는 design-review가 찍을 주소입니다.

## 설계 원칙

1. **도구는 플러그인, 데이터는 프로젝트.** 훅·에이전트·스킬은 플러그인 캐시에 있고, 프로젝트에는 설정·도메인 문서·코드맵만 남습니다. 플러그인을 업데이트하면 모든 프로젝트에 반영됩니다.
2. **검증기는 에이전트 손이 닿지 않는 곳에.** 훅 스크립트가 저장소 밖에 있고, 플러그인 디렉터리 수정은 게이트가 막습니다. 하네스 자체를 개발할 때만 `HARNESS_DEV=1 claude`로 풉니다 (훅은 Claude Code 프로세스 환경을 물려받으므로 에이전트가 이 값을 켤 수 없습니다).
3. **비밀값은 경계에서.** 에이전트는 `.env`를 읽지 않습니다. 더 단단하게 하려면 `.env`에 값 대신 참조(`op://...`)를 두고 `op run`으로 실행 시점에 주입합니다 (`/harness-core:harden`).
4. **막을 땐 이유와 대안을.** 차단 메시지가 모델에 그대로 전달되므로, 우회 대신 올바른 길로 돌아오게 씁니다.
5. **성공은 조용히.** 통과한 검증은 컨텍스트에 아무것도 남기지 않습니다. 감사 로그도 프로젝트가 아니라 플러그인 데이터 디렉터리에 쌓입니다.

## 한계

- `bash_gate`는 명령 문자열을 해석하는 방식이라 모든 우회를 막지는 못합니다. 스크립트 파일을 만들어 실행하는 식의 간접 경로는 보이지 않습니다. OS 수준 격리가 필요하면 Claude Code 샌드박스(`/sandbox`)를 함께 켜세요.
- 행동이 사용자 의도와 맞는지 판정하는 분류기는 하네스가 다시 만들지 않습니다. Claude Code의 auto 권한 모드를 쓰세요.
- 클라우드 세션(claude.ai/code)은 로컬에 설치한 플러그인을 불러오지 않습니다.
- Codex CLI 쪽에서는 실시간 차단이 없습니다. AGENTS.override.md로 예방하고 Claude 쪽에서 사후 검출합니다.
- 워크플로우는 Claude Code의 동적 워크플로우 기능이 켜져 있어야 돕니다. Pro 요금제는 `/config`의 Dynamic workflows에서 켭니다.
- frontend-design은 하드 의존성으로 걸지 않았습니다. 다른 마켓플레이스 플러그인을 의존성으로 걸면, 그 마켓플레이스가 등록되지 않은 환경에서 harness-design 전체가 로드되지 않기 때문입니다.

## 개발

```bash
bash tests/run_all.sh            # 회귀 테스트 + claude plugin validate
python3 tools/sync_lib.py        # core의 _lib.py를 다른 플러그인에 복사 (원본만 고칠 것)
claude --plugin-dir plugins/harness-core   # 설치 없이 한 세션만 로드
```

`--plugin-dir`로 full·codex·automation·design을 시험할 때는 기본 꺼짐이라 프로젝트 `.claude/settings.local.json`에
`{"enabledPlugins": {"harness-codex@inline": true}}`처럼 켜 줘야 합니다.

워크플로우는 `tests/workflow_runner.mjs`가 가짜 `agent()`로 실행해 분기·반복·중단 조건을 검사합니다.
게이트는 세 가지 변형으로 검사합니다: 평범한 개발 명령(오탐 없음), 주입된 지시가 시킬 법한 명령(시크릿 읽기·외부 전송), 요청보다 더 나가는 명령(검증기 끄기·강제 푸시·광범위 삭제).
