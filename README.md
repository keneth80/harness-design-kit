# Harness Design Kit v2

Claude Code용 하네스를 **플러그인 마켓플레이스**로 묶은 저장소입니다.
한 번 설치하면 모든 프로젝트에 보안 게이트가 깔리고, 필요한 프로젝트에서만 워크플로우와 에이전트 팀을 켭니다.

> **처음이라면 [사용 가이드](docs/GUIDE.md)부터 보세요.** 상황별로 어떤 명령을 쓰는지 정리돼 있습니다. 설치한 뒤에는 `/harness-core:help`에 하고 싶은 일을 적으면 명령을 골라 줍니다.
>
> v1(템플릿 복사 + scaffold.sh)에서 옮겨오는 경우 [docs/MIGRATION.md](docs/MIGRATION.md)를 먼저 보세요.

## 한눈에

| 플러그인 | 켜는 범위 | 하는 일 |
|---|---|---|
| **harness-core** | 사용자 전체 (항상) | 시크릿·외부 전송·검증기 변조를 막는 보안 게이트, 편집 후 검증, 코드맵, 도메인 설계 사이클 |
| **harness-full** | 프로젝트별 | 풀 사이클 단계 스킬과 작업자 에이전트 5종, **오케스트레이션 워크플로우 3종**, 종료 전 백프레셔 |
| **harness-codex** | 프로젝트별 | Claude는 설계만, 구현은 Codex CLI. 코드 쓰기 차단 + AGENTS.override.md 내보내기 |
| **harness-automation** | 프로젝트별 | 브라우저 자동화·외부 API 연동·장시간 파이프라인 스킬 |
| **harness-design** | 프로젝트별 | 디자인 브리프·토큰·design_guard·4종 스크린샷 측정·design-critic 채점, 시안 경쟁 워크플로우 |

비유하면 harness-core는 몸에 차는 **공구벨트**(어느 현장에 가든 따라옴), 나머지는 현장에 가져가는 **장비 상자**입니다.
그 현장에서만 의미 있는 규칙(예: 특정 서비스의 셀렉터)은 그 프로젝트의 `.claude/`에 둡니다.

## 요구 환경

| 필요한 것 | 쓰는 곳 | 없으면 |
|---|---|---|
| Claude Code | 전체 | — |
| Python 3.9 이상 (`python3`) | 모든 훅 | 훅이 실행되지 않음. 표준 라이브러리만 써서 pip 설치는 필요 없음 |
| Node.js (Playwright가 지원하는 버전) | harness-design 스크린샷 측정, 워크플로우 테스트 | design-review가 축소 모드로 진행, design-polish는 시작하지 않음 |
| Playwright + Chromium | harness-design | 디자인을 검토할 프로젝트에서 `npm i -D playwright && npx playwright install chromium` |
| Codex CLI | harness-codex | 구현 담당이 없음 |
| 동적 워크플로우 기능 | harness-full·harness-design의 워크플로우 명령 | 명령이 "없는 명령"으로 보임. `/config`의 Dynamic workflows에서 켬 |

- macOS 기본 `/usr/bin/python3`(3.9)는 Xcode Command Line Tools가 있어야 동작합니다. CI가 3.9와 최신 버전에서 모두 테스트합니다.
- 훅은 `PATH`에서 처음 찾은 `python3`를 씁니다. Homebrew Python을 깔아도 `PATH`에서 `/usr/bin`이 `/opt/homebrew/bin`보다 앞이면 3.9가 쓰입니다.
  데스크톱 앱에서 실행되는 훅은 터미널과 `PATH`가 다를 수 있으니, 버전이 중요하면 세션 시작 경고를 확인하세요 (3.9 미만이면 알려줍니다).

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

처음이라면 core만 설치해 며칠 써보고, 나머지는 필요한 프로젝트에서만 켜는 것을 권합니다.

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
게이트의 판정 로직이 오류를 내면 통과시키지 않고 **ask**로 돌립니다. 다음 세션 시작 때 오류 건수를 한 번 알려줍니다.

### deny와 ask가 실제로 보이는 모습

- **ask는 auto 모드에서도 확인 창으로 뜹니다.** 분류기가 허용할 만한 명령이라도 하네스가 ask를 내면 흐름이 멈추고 사용자에게 묻습니다.
  `claude -p` 같은 무인 실행에서는 답할 사람이 없어서 사실상 거부로 끝납니다.
- 확인 창이 너무 자주 뜨면 `/harness-core:audit`로 무엇이 몇 번 걸렸는지 보고 `harness.config.json`을 조정합니다.
  예: 업로드가 일상인 프로젝트면 `security.exfil`, 설정 파일을 자주 고치면 `security.config_edits`, 시크릿이 아닌데 걸리는 파일은 `security.allow_paths`.
- **시크릿 파일은 사용자가 원해도 에이전트가 읽지 않습니다 (deny).** 값이 대화 기록과 모델 컨텍스트에 남지 않게 하려는 설계입니다.
  값이 필요한 작업이면 사용자가 직접 값을 확인하고 키 이름만 알려주거나, `.env.example`에 키 이름을 적어 두세요.
  꼭 열어야 하는 파일이 시크릿 패턴에 잘못 걸린 경우에만 `security.allow_paths`에 추가합니다.

### init한 프로젝트에서만

| 훅 | 시점 | 하는 일 |
|---|---|---|
| `session_start` | 세션 시작 | 하네스 상태 한 줄 + `docs/codemap.md` 주입 |
| `verify_guard` | 편집 직후 | 린트·타입체크 실행, 실패하면 결과를 모델 컨텍스트에 넣음 (차단 안 함) |
| `codemap_refresh` | 응답 종료 | 소스가 바뀌었으면 코드맵 갱신 |

### 루프 안전장치 (v2.4)

루프는 검사기가 정직할 때만 수렴합니다. 그래서 루프가 기대는 두 가지, **통과 판정**과 **시험지**를 에이전트 손에서 뺐습니다.

**통과 기록 원장.** 에이전트가 "통과했어요"라고 보고하는 대신, 스크립트가 검사를 직접 돌리고 결과를 서명해서 남깁니다. 학생이 써낸 "다 맞았어요"가 아니라 채점기가 찍은 도장을 믿는 셈입니다.

```bash
python3 <harness-core>/scripts/verify_run.py           # verify 설정의 검사를 돌리고 원장을 씀
python3 <harness-core>/scripts/verify_run.py --status  # 원장만 확인
```

| state | 뜻 |
|---|---|
| `pass` | 설정된 검사를 모두 통과했고, 그 뒤로 코드가 바뀌지 않았다 |
| `partial-pass` | 통과했지만 설정된 검사 전부는 아니다 (`--cmd`로 한 명령만) |
| `fail` / `stale` | 실패했다 / 원장 이후 코드가 바뀌었다 |
| `tampered` | 서명이 맞지 않는다. 누군가 원장을 손으로 고쳤다 |

- 원장은 `.harness/verify-ledger.json`(자동으로 gitignore), 서명 키는 `~/.claude/harness-data/ledger.key`. 에이전트는 원장을 쓸 수 없고 키는 읽을 수도 없습니다 (file_gate·bash_gate가 deny).
- fix-until-green은 검사 에이전트의 보고가 통과여도 **다른 에이전트(haiku)가 원장을 다시 읽어** 맞을 때만 끝냅니다. full-cycle은 code-verifier의 판단과 원장이 둘 다 pass여야 완료입니다.
- backpressure는 원장이 지금 코드 그대로 pass면 검사를 다시 돌리지 않고, 직접 돌린 결과도 원장에 남깁니다.
- "지금 코드 그대로"는 git HEAD와 작업 트리로 판단합니다. 하네스 산출물(코드맵, 검증 리포트, `_workspace/`)은 빼고 보며, 프로젝트가 만드는 생성물은 `loop.fingerprint_ignore`로 더 뺄 수 있습니다.

**시험지 보호.** 루프의 대표적인 실패는 테스트를 고쳐서 통과하는 것입니다. init한 프로젝트에서는 이런 변경이 확인 창(ask)으로 넘어갑니다. `claude -p` 같은 무인 실행에서는 거부됩니다.

| 대상 | 기본 경로 | ask가 되는 변경 |
|---|---|---|
| 테스트 | `tests/**`, `test_*.py`, `*_test.py`, `*.test.*`, `*.spec.*`, `*_test.go`, `conftest.py` 등 | skip·only 표시 추가, 단언이나 테스트 수 감소, 기존 파일 삭제·셸로 덮어쓰기 |
| 동결 | `golden/**`, `__snapshots__/**`, `*.snap` | 어떤 수정이든 (사람이 정한 정답 데이터) |

테스트를 새로 쓰거나 단언을 늘리는 것은 막지 않습니다. 경로는 `loop.test_paths`·`loop.frozen`으로 바꾸고, 끄려면 `"loop": {"protect_tests": false}`.
스크립트가 파일을 직접 고치는 경로(예: 기대값을 다시 만드는 생성 스크립트, 스냅샷 갱신 명령)는 게이트가 보지 못합니다. 그런 도구로 정답 데이터를 바꿨다면 `git diff`로 사람이 확인하세요.

**프로젝트에 맞추기.** 루프가 믿을 두 가지는 프로젝트마다 다릅니다. `/harness-core:init`이 아래 진단을 돌려 제안하고, 확인을 받아 적용합니다. 직접 해도 됩니다.

```bash
python3 <harness-core>/scripts/loop_setup.py                          # 진단만 (바꾸지 않음)
python3 <harness-core>/scripts/loop_setup.py --write-verify           # 감지한 검사 명령을 verify에 적기
python3 <harness-core>/scripts/loop_setup.py --freeze "data/expected/**"   # 정답 데이터 동결
```

1. **검사 명령 (`verify`)**: 원장이 "통과"를 판단하는 기준입니다. package.json 스크립트, pyproject·requirements(pytest), Cargo, go.mod에서 감지하고, 없으면 직접 적습니다.
   ```json
   { "verify": { "lint": "ruff check .", "typecheck": "mypy src", "test": "python3 -m pytest -q", "timeout": 300 } }
   ```
2. **정답 데이터 (`loop.frozen`)**: 사람이 정한 기대값이 있는 곳입니다. 이름만으로 확실한 것(`golden/**`, `__snapshots__/**`, `*.snap`, `*.golden`, `*.approved.*`)은 기본으로 동결하고,
   `expected/`·`baseline/`·`reference/`처럼 입력 데이터일 수도 있는 폴더는 후보로만 보여줍니다. 정답이 맞는 것만 더하세요.
   ```json
   { "loop": { "frozen": ["golden/**", "__snapshots__/**", "*.snap", "*.golden", "*.golden.*", "*.approved.*", "data/expected/**"] } }
   ```
   프로젝트 설정의 목록은 기본값을 **대체**하므로 직접 적을 때는 기본값도 함께 적으세요 (`--freeze`는 알아서 합칩니다).
3. 테스트 파일 이름 규칙은 Python·JS/TS·Go·Java/Kotlin·C#·Ruby·Scala·PHP·Swift·Dart·Elixir를 기본으로 알고, 나머지는 `--test-path`로 더합니다.

**시나리오 검사 (v2.5).** 단위 테스트가 부품 검사라면 시나리오는 완성품을 켜 보는 검사입니다. `harness.scenarios.json`에 "그러면 이렇게 된다"를 명령이나 HTTP 요청으로 적습니다.

```json
{ "scenarios": [
  { "id": "home", "then": "홈이 열린다", "tags": ["local"], "check": { "type": "http", "url": "${BASE_URL}/" } },
  { "id": "api", "then": "API가 응답한다", "needs": ["home"], "check": { "type": "http", "url": "${BASE_URL}/health", "expect": { "contains": "ok" } } },
  { "id": "live", "then": "운영이 새 버전이다", "tags": ["deploy"], "check": { "type": "http", "url": "${PROD_URL}/version", "expect": { "contains": "1.4.0" } },
    "risk": { "impact": "전체 사용자", "recovery": "직전 버전으로 재배포", "recoveryChecks": ["home"] } }
] }
```

- `needs`: 앞 시나리오가 통과해야 돈다. 실패하면 뒤는 `blocked`로 남아서 원인이 하나로 좁혀집니다.
- `${변수}`: 환경마다 다른 주소·토큰. 값이 없으면 `skipped`이고 통과로 치지 않습니다.
- `risk`: 되돌리기 어려운 작업이 실패하면 영향, 복구 방법, 복구 확인 결과를 함께 보여줍니다. 복구 자체는 실행하지 않습니다.
- `verify`에 `"scenarios": ["local"]`(태그·id) 또는 `true`를 넣으면 원장에 묶여서 루프·`/goal`·backpressure의 통과 기준이 됩니다. 배포 뒤 확인은 `scenario_run.py --only deploy`로 따로 돌리세요.
- 이 파일은 검증 기준이라 에이전트가 고치면 확인 창이 뜹니다. `/harness-core:scenarios`가 스펙과 스크립트를 읽어 초안을 만들어 줍니다.
- 시나리오의 선후 관계와 위험·복구 기록은 [vibe](https://github.com/su-record/vibe)의 시나리오 방식에서 아이디어를 얻었습니다.

**목표 루프.** `/harness-core:goal`이 Claude Code의 `/goal`에 원장 조건과 반복 상한을 붙여 겁니다. 예: "verify_run.py와 --status가 모두 pass, 테스트·골든 데이터 약화 없음, 12번 넘으면 멈추고 보고".

### 스킬 (`/harness-core:<이름>`)

| 스킬 | 용도 |
|---|---|
| `help` | 하고 싶은 일에 맞는 명령 1~3개 추천 |
| `init` | 이 프로젝트에 워크플로우 켜기, v1 잔재 정리 |
| `verify` | code-verifier(haiku)로 4개 레이어 검증 → `docs/verification-report.md` |
| `code-review` | 오너의 이해를 위한 워크스루 (의도 순서 요약, 읽기 가이드, 이해 확인 질문) |
| `security-review` | security-reviewer(opus)로 권한 매트릭스·IDOR·RLS 점검 |
| `domain-interview` → `domain-manual` → `domain-refactor` | 도메인 설계 사이클 |
| `dev-start` | 현재 상태 파악 + 다음 작업 3개 |
| `lessons` | 오류 기록, 반복되면 교훈으로 승격, 조회 ("또 안 되네"라고만 해도 켜짐) |
| `codemap` | 코드맵 지금 다시 만들기 |
| `audit` | 게이트가 무엇을 왜 막았는지 요약 |
| `harden` | Claude Code 권한 deny 규칙·샌드박스·시크릿 참조 패턴 안내 |
| `goal` | `/goal` 루프를 원장 조건과 반복 상한에 묶어서 걸기 |
| `scenarios` | 완성품을 켜서 확인하는 시나리오 검사 만들기·실행 (needs, 위험·복구) |

에이전트: `code-verifier`(haiku), `security-reviewer`(opus). 둘 다 만든 쪽과 따로 채점하는 독립 검수자입니다.

### 도메인 설계 사이클

AI 코딩의 흔한 실패는 "설계 모순을 안은 채 코드부터 짜고, 나중에 발견해서 크게 갈아엎기"입니다.

```
domain-interview  →  docs/domains/<도메인>/interview.json   (슬롯 채우기 + 모순 검출, complete까지 유한 루프)
domain-manual     →  docs/domains/<도메인>/manual.md        (불변 규칙·의존 계약·결정 근거, code_paths)
drift_guard       →  code_paths의 코드는 인터뷰가 complete일 때만 수정 허용
domain-refactor   →  매뉴얼 기준으로 코드 진단 (report 모드)
```

## harness-full

켜면 단계별 스킬이 추가되고, 응답을 끝내기 전에 백프레셔가 린트·타입체크·테스트를 돌립니다.

| 단계 | 명령 | 어디서 도나 |
|---|---|---|
| 정렬 | `grill` (직접 부를 때만: 가정을 먼저 보여주고 비싼 것만 최대 3개 질문) | 메인 대화 |
| 벤치마크 | `benchmark` | 둘러보기 스크립트 + benchmark-analyst 작업자(sonnet, 사이트마다 병렬) → 역제안은 메인 대화 |
| 기획 | `plan-start` | 메인 대화 (opus, 사용자와 직접 대화) |
| 골격 | `architect` | architect 작업자 (opus, 따로 떨어져 작업) |
| UI | `ui-design` | 메인 대화 |
| 테스트 | `test-cases`, `tdd` | qa-tester 작업자 (haiku) / 메인 대화 |
| 구현 | `full-cycle`(워크플로우), `orchestrator`(대화형) | backend-dev, frontend-dev 작업자 (sonnet, 병렬) |
| 경계 | `qa-boundary` | qa-engineer 작업자 (haiku, 읽기 전용) |
| 문제 | `diagnose`, `error-recovery`, `architecture` | 메인 대화 |

### 스킬과 에이전트 (v2.7)

노하우는 전부 스킬에 있고, 에이전트는 **독립 채점**(code-verifier, security-reviewer, design-critic)과 **병렬 작업자**(architect, qa-tester, qa-engineer, backend-dev, frontend-dev), **세션 모드**(design-lead)에만 남겼습니다.

- 작업자 에이전트 파일은 모델과 도구만 정한 껍데기이고, 절차는 숨은 작업 교본 스킬(`architect-playbook`, `backend-playbook` 등, `user-invocable: false`)에 한 번만 있습니다. 에이전트가 `skills:`로 미리 불러옵니다.
- `/harness-full:architect`, `test-cases`, `qa-boundary`는 `context: fork`로 해당 작업자에게 따로 떨어져 돌고 결과만 돌려줍니다.
- 기획과 화면 설계는 메인 대화에서 돌아서, 질문이 생기면 바로 사용자에게 묻습니다 (에이전트는 실행 중에 사용자에게 물을 수 없습니다).
- 플러그인 스킬의 `context: fork`가 동작하는 Claude Code 버전이 필요합니다 (2.1.319에서 확인).

모델은 `opus`·`sonnet`·`haiku` 별칭으로 지정해서 새 모델이 나와도 파일을 고칠 필요가 없습니다.
백프레셔는 같은 세션에서 3번 연속 막아도 계속 실패하면 멈추고 사용자에게 넘깁니다. 끄려면 `"backpressure": {"enabled": false}`.

### 벤치마크 역제안 (v2.8)

`/harness-full:benchmark <URL> [알고 싶은 것]`은 잘되는 가게에 손님으로 가서 동선과 메뉴판을 적어 온 뒤, 우리 가게에 가져올 것을 먼저 제안하는 기능입니다.

1. **둘러보기** (`bench_crawl.mjs`, Playwright): 같은 사이트의 공개 페이지만 최대 20쪽. robots.txt(Crawl-delay 포함)를 지키고 요청 사이 1.5초 간격, 봇임을 숨기지 않습니다. 로그인·폼 제출·입력은 하지 않고, 로그아웃·삭제처럼 상태를 바꿀 수 있는 주소는 열지 않습니다.
   모으는 것: 메뉴 구조, 페이지별 제목·버튼 문구(80자까지), 폼 구조(입력값은 읽지 않음), 랜드마크, API 호출 패턴(`GET /api/items/:id`), 외부 서비스 호스트, 앞쪽 페이지의 데스크톱·모바일 스크린샷(`shots/`, 자동 gitignore)
2. **분석** (benchmark-analyst, 사이트마다 병렬): 기능 목록, 주요 흐름, 배울 점, 약점, 못 본 것. 모든 항목에 **확인됨·추정·모름** 판정과 근거
3. **역제안** (메인 대화): 우리 목표·기획서에 비춰 **가져올 것·다르게 할 것·안 할 것**을 제안하고 사용자가 고릅니다
4. **이어가기**: 고른 기능의 시나리오 초안(`docs/benchmark/scenarios.draft.json`)을 `/harness-core:scenarios`로 확정하면, 구현 후 그 흐름이 실제로 동작하는지 원장으로 확인됩니다

문구·이미지·로고·코드는 가져오지 않고 패턴과 동작만 다룹니다. 이용약관에 자동 수집 금지 문구가 보이면 멈추고 묻습니다 (법적 판단은 하지 않습니다).
Node·Playwright가 없으면 WebFetch만 쓰는 얕은 모드로 진행합니다. 앱·데스크톱 프로그램처럼 웹이 아닌 대상은 다루지 않습니다 ([REA](https://github.com/morluto/rea) 같은 전용 도구 안내만).

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
| 눈 | `/harness-design:design-review` 모바일·데스크톱 × 라이트·다크 4종 스크린샷 + 명도 대비·가로 넘침·터치 영역·이름 없는 컨트롤·출시 점검(lang, title, og:image, `<main>`, 본문 바로가기, 한글 제목 줄바꿈) 측정 → design-critic(opus)이 8개 항목으로 채점 → 상위 3개 수정 → 다시 찍기 (최대 3라운드) |

**랜딩 페이지**는 보이는 것만큼 말하는 것이 중요합니다. `/harness-design:landing-page`가 사전 질문(행동 하나, 반론 세 가지, 유입 경로, 증거), 섹션 순서, 레이아웃 유형 네 가지, 전환 문구, SEO/AEO를 정하고 `docs/design/landing-copy.md`에 문구부터 쓴 뒤 섹션 하나씩 만듭니다.
랜딩·마케팅 페이지일 때만 켜지고, 서체·색·간격은 정하지 않습니다 (브리프와 토큰이 정함).
모든 화면에 공통인 **마감 기준**(실제 같은 콘텐츠, 상태 6종, 출시 전 목록, 겹친 반경·줄바꿈·움직임 규칙)은 `design-review/references/finish.md`에 있고, design-critic이 채점할 때 함께 봅니다.
이 두 문서는 [elayadesign/ai-design-skills](https://github.com/elayadesign/ai-design-skills)(MIT)의 일부를 옮기고 고친 것입니다. 고지는 `plugins/harness-design/THIRD_PARTY_NOTICES.md`.

**`/harness-design:design-polish` 워크플로우**는 오케스트레이션과 디자인을 합친 것입니다.
서로 확실히 다른 방향의 시안 2~4개를 HTML 목업으로 만들고, 브랜드·사용성·완성도 관점의 심사위원 3명이 이름을 가린 채 채점해 1위를 고른 뒤, 비평 → 수정 → 재촬영을 반복합니다. 실제 코드는 바꾸지 않고, 적용은 사용자가 고른 뒤에 합니다.

```text
/harness-design:design-polish 예약 랜딩 첫 화면
```

- 스크린샷 측정에는 **Node.js와 Playwright**가 필요합니다. `node "<harness-design>/scripts/capture.mjs" --check`로 준비 상태를 볼 수 있고, design-review가 첫 단계에서 이 점검을 합니다.
  설치를 원하지 않으면 design-review는 축소 모드(Browser pane이나 직접 준 스크린샷으로 채점, 수치 측정 생략)로 진행하고, design-polish는 비싼 단계 전에 멈춥니다.
- 데스크톱 앱에서는 Browser pane의 자동 검증(`.claude/launch.json`)도 함께 쓰면 편집할 때마다 화면을 확인합니다.
- design-polish는 에이전트를 8~13개 띄우고 심사는 opus로 돌아서, 일반 대화보다 토큰을 훨씬 많이 씁니다. 시안 2개·라운드 1회로 먼저 시험해 보세요 (`variants`, `rounds` 인자).

## harness-automation

`browser-automation`(Playwright·CDP 연결과 구현 절차), `integration`(외부 SDK·요청 한도·비용), `pipeline`(체크포인트·재시작·작업 큐), `task-routing`, `browser-status` 스킬.
관련 작업을 말하면 자동으로 켜집니다. 특정 서비스용 규칙은 [examples/jarvis-chatbot](examples/jarvis-chatbot)처럼 프로젝트 `.claude/`에 둡니다.

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

## 비용과 지연

훅은 정해진 시점에 돌고, 아래 타임아웃은 **최대치**입니다. 대부분의 경우 훨씬 빨리 끝나거나 아예 건너뜁니다.

| 훅 | 시점 | 최대 | 실제로는 |
|---|---|---|---|
| `bash_gate`·`file_gate`·`drift_guard` | 도구 실행 전 | 10초 | 수십 ms. 외부 명령을 실행하지 않음 |
| `verify_guard` | 편집 직후 (init 프로젝트) | 150초 | `verify.run_on`에 맞는 파일만, 린트·타입체크만 (테스트는 기본으로 안 돌림, `skip_test_on_edit`) |
| `codemap_refresh` | 응답 종료 (init 프로젝트) | 70초 | 소스가 코드맵보다 새로울 때만 |
| `backpressure` | 응답 종료 (harness-full) | 600초 (검사당 180초) | git 상태가 지난번과 같으면 건너뜀. 3번 연속 실패하면 멈춤 |
| `task_gate` | 팀원 작업 완료 (harness-full) | 300초 | 에이전트 팀을 쓸 때만, 린트·타입체크만 |

토큰을 많이 쓰는 것은 훅이 아니라 워크플로우입니다. design-polish는 에이전트 8~13개를 띄우고 심사는 opus로 돌립니다 (시안 2개·라운드 1회로 시작해 보세요).
full-cycle은 기능 수에 비례해 에이전트가 늘어납니다.

**가볍게 시작하는 설정.** 처음에는 편집 직후 검사를 좁히고 백프레셔를 끈 채로 써보고, 익숙해지면 넓힙니다.

```json
{
  "version": 2,
  "verify": { "typecheck": "npx tsc --noEmit", "run_on": ["src/**/*.ts", "src/**/*.tsx"] },
  "backpressure": { "enabled": false },
  "codemap": { "enabled": true }
}
```

## Claude Code 내장 기능과의 관계

하네스는 내장 기능을 대신하지 않고 옆에서 보완합니다. 내장 명령 이름은 Claude Code 2.1.316 기준입니다.

| 내장 | 하네스 | 언제 무엇을 |
|---|---|---|
| `/code-review` (`/review`) | `/harness-core:code-review` | 버그와 정리할 점을 찾을 때는 내장. 바뀐 코드를 오너가 이해하는 게 목적이면 하네스 (의도 순서 요약, 읽기 가이드, 이해 확인 질문) |
| `/security-review` | `/harness-core:security-review` | 변경분의 일반 보안 점검은 내장. 권한 매트릭스·IDOR·RLS를 opus 에이전트로 깊게 볼 때는 하네스 |
| auto 모드 분류기 | `bash_gate`·`file_gate` | 분류기는 사용자 의도와 맞는지 판단, 하네스는 규칙대로 결정적으로 차단. 함께 쓰는 것을 권장 |
| `/sandbox` | — | OS 수준 격리. 스크립트 파일을 만들어 실행하는 식의 간접 경로처럼 `bash_gate`가 못 보는 것을 막음 |
| 데스크톱 앱 Browser pane | `capture.mjs` | 편집하며 화면 확인은 Browser pane. 모바일·데스크톱 × 라이트·다크 4종과 대비·넘침·터치 영역 수치는 capture |

## 문제 해결

업데이트 후 갑자기 확인 창이 많아지거나 정상 명령이 막히면, harness-core는 사용자 범위라 모든 프로젝트가 같은 영향을 받습니다. 먼저 [CHANGELOG](CHANGELOG.md)의 **동작 변경**을 확인하세요.

| 하고 싶은 것 | 방법 |
|---|---|
| 무엇이 왜 막혔는지 보기 | `/harness-core:audit` 또는 감사 로그 `~/.claude/plugins/data/harness-core*/audit.jsonl` (deny·ask·error는 항상 기록, 통과까지 보려면 `HARNESS_MONITOR=1 claude`) |
| 이 프로젝트에서만 끄기 | `claude plugin disable harness-core@harness-design-kit --scope local` |
| 전부 끄기 | `claude plugin disable harness-core@harness-design-kit` |
| 하네스 자체를 고치며 쓰기 | `HARNESS_DEV=1 claude` (플러그인 디렉터리 수정 허용) |

- 끄는 명령은 **본인 터미널에서 직접** 실행하세요. Claude에게 시키면 `bash_gate`가 확인 창을 띄웁니다 (검증기를 끄는 행동이라).
- 게이트가 계속 "판정 오류"로 확인을 요청하면 `harness.config.json` 형식(목록 자리에 문자열·숫자가 들어갔는지)과 `python3 --version`을 먼저 보세요.

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
  꺼져 있으면 워크플로우 명령이 "없는 명령"으로 보입니다. 하네스는 이때 Claude가 즉석에서 대신 수행하지 않고 안내하도록 세션 컨텍스트와 CLAUDE.md 구역에 규칙을 넣어 둡니다.
- 훅이 타임아웃되거나 `python3`를 찾지 못하면 Claude Code는 그 훅을 건너뛰고 진행합니다. 하네스 안에서는 막을 수 없는 경로라, 세션 시작 경고와 감사 로그로 드러나게 합니다.
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
