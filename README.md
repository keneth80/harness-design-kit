# Harness Design Kit v2

Claude Code용 하네스를 **플러그인 마켓플레이스**로 묶은 저장소입니다.
한 번 설치하면 모든 프로젝트에 보안 게이트가 깔리고, 필요한 프로젝트에서만 워크플로우와 에이전트 팀을 켭니다.

> v1(템플릿 복사 + scaffold.sh)에서 옮겨오는 경우 [docs/MIGRATION.md](docs/MIGRATION.md)를 먼저 보세요.

## 한눈에

| 플러그인 | 켜는 범위 | 하는 일 |
|---|---|---|
| **harness-core** | 사용자 전체 (항상) | 시크릿·외부 전송·검증기 변조를 막는 보안 게이트, 편집 후 검증, 코드맵, 도메인 설계 사이클 |
| **harness-full** | 프로젝트별 | 풀 사이클 에이전트 팀 8종, 기획→스캐폴딩→테스트→경계검증 스킬, 종료 전 백프레셔 |
| **harness-codex** | 프로젝트별 | Claude는 설계만, 구현은 Codex CLI. 코드 쓰기 차단 + AGENTS.override.md 내보내기 |
| **harness-automation** | 프로젝트별 | 브라우저 자동화·외부 API 연동·장시간 워크플로우 전문 에이전트 3종 |

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
| 구현 | `orchestrator` | backend-dev, frontend-dev (sonnet) |
| 경계 | `qa-boundary` | qa-engineer (haiku) |
| 문제 | `diagnose`, `error-recovery`, `architecture` | error-handler (sonnet) |

모델은 `opus`·`sonnet`·`haiku` 별칭으로 지정해서 새 모델이 나와도 파일을 고칠 필요가 없습니다.
백프레셔는 같은 세션에서 3번 연속 막아도 계속 실패하면 멈추고 사용자에게 넘깁니다. 끄려면 `"backpressure": {"enabled": false}`.

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
  "automation": { "cdp_ports": [9222, 9223] }
}
```

- `drift_guard.mode`: `block`(기본) · `warn`(차단을 경고로) · `off`. `warn_paths`는 해당 경로만 경고로.
- `verify`: 비우면 package.json 스크립트·ruff·mypy·cargo·go로 자동감지. 편집마다 테스트를 돌리려면 `"skip_test_on_edit": false`.
- `security.exfil`, `config_edits`: `ask` 또는 `deny`. `secret_paths`를 지정하면 기본 목록을 대체합니다.

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

## 개발

```bash
bash tests/run_all.sh            # 회귀 테스트 + claude plugin validate
python3 tools/sync_lib.py        # core의 _lib.py를 다른 플러그인에 복사 (원본만 고칠 것)
claude --plugin-dir plugins/harness-core   # 설치 없이 한 세션만 로드
```

`--plugin-dir`로 full·codex·automation을 시험할 때는 기본 꺼짐이라 프로젝트 `.claude/settings.local.json`에
`{"enabledPlugins": {"harness-codex@inline": true}}`처럼 켜 줘야 합니다.

테스트는 세 가지 변형으로 게이트를 검사합니다: 평범한 개발 명령(오탐 없음), 주입된 지시가 시킬 법한 명령(시크릿 읽기·외부 전송), 요청보다 더 나가는 명령(검증기 끄기·강제 푸시·광범위 삭제).
