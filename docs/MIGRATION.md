# v1 → v2 마이그레이션

v1은 템플릿 폴더를 프로젝트에 통째로 복사했습니다. v2는 같은 기능을 플러그인으로 설치하고, 프로젝트에는 그 프로젝트의 내용물만 남깁니다.

## 무엇이 어디로 갔나

| v1 | v2 |
|---|---|
| `scaffold.sh` + `template/`, `template-universal/` | 마켓플레이스 + `/harness-core:init` |
| `.claude/profiles/switch.sh lite\|full` | `claude plugin enable/disable harness-full@harness-design-kit --scope local` |
| `.claude/hooks/security_gate.py` | `harness-core` bash_gate (토큰 단위 해석, 우회·오탐 수정) |
| `.claude/hooks/secret_scan.py` (쓰고 난 뒤 경고) | `harness-core` file_gate (쓰기 **전** 차단 + Read 도구로 .env 열기 차단) |
| `.claude/hooks/drift_guard.py` | `harness-core` drift_guard (deny JSON, 경로 경계 버그 수정) |
| `.claude/hooks/verify_guard.py` | `harness-core` verify_guard (결과가 실제로 모델에 전달됨) |
| `.claude/hooks/codemap*.py` | `harness-core` session_start, codemap_refresh, `/harness-core:codemap` |
| `.claude/hooks/backpressure.py` | `harness-full` backpressure (변경 없을 땐 생략, 3회 후 중단) |
| `.claude/hooks/code_reviewer.py`, `report_generator.py`, `verifier-scripts/` | 은퇴. `/harness-core:verify`와 `/harness-core:audit`로 대체 |
| `.claude/hooks/monitor*.py`, `/monitor`, `/verify-report` | `/harness-core:audit` (`HARNESS_MONITOR=1`은 그대로) |
| `.claude/verify.json` | `harness.config.json`의 `verify` (v1 파일도 계속 읽음) |
| `harness.config.json`의 `profile` | 제거 (플러그인 켜고 끄기로 대체) |
| `.claudeignore` | 삭제. Claude Code가 읽지 않는 파일입니다. 시크릿 차단은 file_gate가, 더 단단하게는 `/harness-core:harden`의 Read deny 규칙이 맡습니다 |
| `/verify` `/code-review` `/security-review` `/dev-start` `/lessons` | `/harness-core:verify` 등 같은 이름 |
| `/grill` `/plan-start` `/architect` `/ui-design` `/tdd` `/test-cases` `/qa-boundary` `/diagnose` | `/harness-full:…` 같은 이름 |
| optional 에이전트 (browser-dev, integration-dev, automation-dev) | `harness-automation` |
| `claude-codex-harness` 저장소 | `harness-codex` |
| JARVIS 챗봇 전용 스킬·규칙 | `examples/jarvis-chatbot/` → 그 프로젝트의 `.claude/`로 |
| `setup-claude-optimization.sh` | 은퇴 (Opus 4.7 시절 환경변수 튜닝) |

## v1에서 고친 문제

- **검증기가 저장소 안에 있었다.** 에이전트가 쓸 수 있는 `.claude/hooks/`에 있어서 "검증기는 못 고친다"는 원칙이 구조로 보장되지 않았습니다. 이제 플러그인 캐시에 있고 수정이 차단됩니다.
- **security_gate 우회와 오탐.** `head .env`, `python3 -c "open('.env')"`, `curl --data @.env`가 통과했고 `git commit -m 'fix reboot'`이 막혔습니다.
- **secret_scan이 사후 검사였다.** PostToolUse라 이미 써진 뒤에 경고했습니다.
- **verify_guard 경고가 모델에 안 보였다.** PostToolUse의 일반 stdout은 모델에 전달되지 않습니다. 이제 additionalContext로 냅니다.
- **스킬 frontmatter의 `trigger`.** Claude Code가 읽지 않는 필드라 스킬 자동 선택에 쓰이지 않았습니다. 모든 스킬에 `description`과 `when_to_use`를 달았습니다.
- **모델 ID 고정.** `claude-opus-4-7` 등 14곳을 `opus`·`sonnet`·`haiku` 별칭으로 바꿨습니다.
- **drift_guard 경로 매칭.** `src/auth`가 `src/authz`까지 잡았고, `last_synced:` 줄 끝 주석이 날짜 값에 섞였습니다.
- **두 저장소 갈라짐.** `claude-codex-harness`에 같은 스킬·훅이 복제돼 따로 바뀌고 있었습니다. 이제 core에 의존하는 플러그인 하나입니다.

## 기존 프로젝트 옮기기

1. 플러그인 설치 (README의 설치 절차).
2. 프로젝트에서 `claude` 실행 후 `/harness-core:init`.
   - `harness.config.json`을 v2로 갱신하고 `.claude/verify.json` 내용을 옮깁니다 (원본은 남김).
   - CLAUDE.md에 하네스 구역을 넣습니다. 기존 내용은 그대로 둡니다.
   - v1 흔적이 있으면 `!` 줄로 알려줍니다.
3. init 스킬의 "v1 정리" 절차를 따릅니다. 핵심은 `.claude/settings.json`의 v1 훅 등록을 지우는 것입니다. 남겨두면 플러그인 훅과 이중으로 돕니다.
4. 프로젝트 전용으로 만든 스킬·규칙(`.claude/skills/chatbot-ui` 같은 것)은 그대로 둡니다.
5. full 프로파일을 쓰던 프로젝트면 `claude plugin enable harness-full@harness-design-kit --scope local`.
6. `/harness-core:audit`로 며칠간 무엇이 막히는지 보고, 오탐이면 `security.allow_paths` 등으로 조정합니다.

## 그대로인 것

- `docs/domains/` 구조, interview.json·manual.md 형식, 매뉴얼 고정 섹션
- `docs/lessons-learned.md`, `docs/error-log.md`, error-curator 승격 규칙
- `_workspace/` 보고서 규칙 (harness-full)
- `docs/codemap.md` 형식
- `HARNESS_MONITOR=1`
