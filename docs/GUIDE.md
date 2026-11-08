# 하네스 사용 가이드

처음 쓰는 사람을 위한 안내서입니다. 설정의 세부 값과 동작 원리는 [README](../README.md)에 있습니다.

## 하네스가 뭔가요

Claude Code에 끼우는 작업 장비입니다. 비유하면 이렇습니다.

- **harness-core**는 몸에 차는 **공구벨트**입니다. 한 번 설치하면 어느 프로젝트에 가든 따라오고, 시크릿을 읽거나 검사를 속이는 행동을 막습니다.
- **나머지 플러그인**은 현장에 가져가는 **장비 상자**입니다. 필요한 프로젝트에서만 켭니다.

| 플러그인 | 언제 켜나 |
|---|---|
| harness-core | 항상 (모든 프로젝트) |
| harness-full | 기획부터 구현·검증까지 단계별로 진행하는 프로젝트 |
| harness-design | 화면 품질이 중요한 프로젝트 |
| harness-codex | 설계는 Claude, 구현은 Codex로 나누고 싶을 때 |
| harness-automation | 브라우저 자동화, 외부 API 연동, 오래 도는 작업 |

## 5분 시작

```bash
claude plugin marketplace add keneth80/harness-design-kit
claude plugin install harness-core@harness-design-kit          # 모든 프로젝트에
```

프로젝트 폴더에서 Claude Code를 열고:

```
/harness-core:init          이 프로젝트에 하네스 켜기 (검사 명령과 정답 데이터를 같이 정해 줌)
/harness-core:help          지금 뭘 하면 좋을지 1~3개 추천
```

다른 플러그인이 필요하면 그 프로젝트에서만 켭니다:

```bash
claude plugin install harness-full@harness-design-kit
claude plugin enable harness-full@harness-design-kit --scope local
```

**뭘 써야 할지 모르겠으면 언제든 `/harness-core:help`**에 하고 싶은 일을 적으세요. 예: `/harness-core:help 테스트 다 통과시키고 싶어`

## 알아둘 개념 세 가지

| 이름 | 비유 | 하네스에서 |
|---|---|---|
| **스킬** | 업무 매뉴얼 | 거의 모든 기능. `/플러그인:이름`으로 부르거나, 관련 작업이면 Claude가 알아서 꺼내 씁니다 |
| **에이전트** | 따로 일하는 동료 | 두 경우에만: 만든 사람과 **다른 사람이 채점**해야 할 때, 여러 명이 **동시에** 일해야 할 때 |
| **훅** | 안전장치 | 명령이나 파일 수정 직전·직후에 자동으로 돕니다. 부를 필요 없습니다 |

**워크플로우**는 여러 에이전트를 정해진 순서로 돌리는 대본입니다 (`full-cycle`, `fix-until-green`, `domain-sweep`, `design-polish`).
Claude Code 설정(`/config`)에서 Dynamic workflows가 켜져 있어야 합니다.

## 상황별 명령

괄호는 필요한 플러그인입니다. core 외에는 그 프로젝트에서 켜야 보입니다.

### 처음 시작할 때
| 하고 싶은 일 | 명령 |
|---|---|
| 이 프로젝트에 하네스 켜기 | `/harness-core:init` (core) |
| 지금 상태와 다음 할 일 3개 | `/harness-core:dev-start` (core) |
| 뭘 써야 할지 모르겠다 | `/harness-core:help` (core) |

### 만들기 전에
| 하고 싶은 일 | 명령 |
|---|---|
| 큰 작업 전에 내가 원하는 걸 제대로 이해했는지 맞추기 | `/harness-full:grill` (full) |
| 한 줄 목표를 기획서로 | `/harness-full:plan-start` (full) |
| 잘되는 서비스를 둘러보고 가져올 기능을 제안받기 | `/harness-full:benchmark <URL>` (full) |
| 새 시스템이나 여러 영역이 얽힌 설계 | `/harness-core:domain-interview` → `/harness-core:domain-manual` (core) |
| 화면 방향 정하기 | `/harness-design:design-brief` → `/harness-design:design-system` (design) |
| 랜딩 페이지 구조와 문구 | `/harness-design:landing-page` (design) |

### 만들 때
| 하고 싶은 일 | 명령 |
|---|---|
| 기획서대로 처음부터 끝까지 자동으로 | `/harness-full:full-cycle` (full) |
| 같은 흐름을 단계마다 확인하며 | `/harness-full:orchestrator` (full) |
| 빌드 골격과 공유 타입만 | `/harness-full:architect` (full) |
| 화면 설계와 구현 | `/harness-full:ui-design` (full) |
| 테스트부터 | `/harness-full:test-cases`, `/harness-full:tdd` (full) |
| 설계는 Claude, 구현은 Codex | `/harness-codex:codex-handoff` → `/harness-codex:codex-review` (codex) |
| 브라우저 자동화, 외부 API, 장시간 파이프라인 | 관련 작업을 말하면 `browser-automation`, `integration`, `pipeline` 스킬이 켜집니다 (automation) |

### 확인할 때
| 하고 싶은 일 | 명령 |
|---|---|
| 지금 코드가 괜찮은지 | `/harness-core:verify` (core) |
| 통과할 때까지 알아서 고치기 | `/harness-full:fix-until-green` (full) 또는 `/harness-core:goal` (core) |
| 완성품을 켜서 확인, 배포 후 확인 | `/harness-core:scenarios` (core) |
| 바뀐 코드를 내가 이해하기 | `/harness-core:code-review` (core) |
| 보안 구멍 (권한, 남의 데이터 접근) | `/harness-core:security-review` (core) |
| 백엔드와 프론트가 맞물리는지 | `/harness-full:qa-boundary` (full) |
| 정한 설계 규칙을 코드가 어겼는지 | `/harness-core:domain-refactor` (core), 전체는 `/harness-full:domain-sweep` (full) |
| 화면 품질 (스크린샷, 접근성, 채점) | `/harness-design:design-review` (design) |
| 시안 여러 개 겨루기 | `/harness-design:design-polish` (design) |

### 문제가 생겼을 때
| 하고 싶은 일 | 명령 |
|---|---|
| 버그 원인 찾기 | `/harness-full:diagnose` (full) |
| 오류 메시지 해석과 복구 | `/harness-full:error-recovery` (full) |
| 같은 실수가 반복된다 | `/harness-core:lessons` (core). "또 안 되네"라고만 해도 켜집니다 |
| 하네스가 왜 막았지 | `/harness-core:audit` (core) |
| 구조가 꼬였다 | `/harness-full:architecture` (full) |
| 크롬 자동화 연결이 안 된다 | `/harness-automation:browser-status` (automation) |

## 자주 쓰는 흐름

**새로 만드는 프로젝트**
```
/harness-core:init → docs/goal.md에 한 줄 목표 (참고할 사이트가 있으면 /harness-full:benchmark <URL>) → /harness-full:plan-start
→ /harness-full:full-cycle → /harness-core:verify
```

**이미 있는 프로젝트를 검수할 때**
```
/harness-core:init (검사 명령과 정답 데이터 지정) → /harness-core:verify
→ /harness-core:security-review → 실패가 있으면 /harness-full:fix-until-green
```

**화면을 다듬을 때**
```
/harness-design:design-brief → /harness-design:design-system
→ 작업 → /harness-design:design-review (통과할 때까지 최대 3라운드)
```

**통과할 때까지 맡겨 둘 때**
```
/harness-core:goal "결제 모듈 테스트 전부 통과"
```
하네스가 "통과"를 스크립트가 직접 돌린 검사 결과(서명된 원장)로만 판단하고, 테스트를 약하게 고쳐서 통과하는 것은 확인 창으로 막습니다.

## 스킬과 에이전트는 어떻게 나뉘어 있나요 (v2.7)

요즘 모델은 똑똑해서, 일마다 직원을 새로 뽑기보다 유능한 직원 한 명에게 매뉴얼 서랍을 주는 편이 낫습니다.
그래서 하네스의 노하우는 전부 스킬에 있고, 에이전트는 꼭 필요한 곳에만 남겼습니다.

| 에이전트 | 남긴 이유 |
|---|---|
| code-verifier, security-reviewer, design-critic | **독립 채점.** 만든 쪽이 스스로 채점하지 않도록 새 맥락, 읽기 전용 도구로 따로 봅니다 |
| architect, qa-tester, qa-engineer, backend-dev, frontend-dev, benchmark-analyst | **병렬 작업자.** full-cycle이 동시에 띄웁니다. 에이전트 파일은 모델과 도구만 정한 껍데기이고, 절차는 숨은 "작업 교본" 스킬에 있습니다 |
| design-lead (codex) | **세션 모드.** 켜면 메인 Claude가 설계만 하는 역할로 바뀝니다 |

- 사용자는 에이전트를 직접 부를 일이 없습니다. `/harness-full:architect`처럼 명령을 부르면 해당 작업자가 따로 떨어져 일하고 결과만 돌려줍니다.
- 기획(`plan-start`)과 화면 설계(`ui-design`)는 메인 대화에서 돕니다. 질문이 생기면 바로 사용자에게 묻습니다.
- 작업 교본 스킬(`*-playbook`)은 명령 목록에 보이지 않습니다. 작업자가 시작할 때 자동으로 불러옵니다.

## 하네스가 막을 때

| 표시 | 뜻 | 할 일 |
|---|---|---|
| **deny** (거부) | 시크릿 읽기, 하네스 파일 수정, 검사 결과 위조처럼 절대 안 되는 것 | 메시지의 대안을 따르세요. 예: 키 이름은 `.env.example`에서 확인 |
| **ask** (확인 창) | 외부 업로드, 강제 푸시, 설정 수정, 테스트를 약하게 만드는 변경처럼 사람이 판단할 것 | 내용을 보고 허용하거나 거절하세요 |
| **판정 오류로 확인 요청** | 하네스 자체에 문제가 생겨 검사를 못 했을 때 | 허용 여부를 직접 판단하고, 반복되면 `/harness-core:audit` |

자주 걸리면 `/harness-core:audit`로 무엇이 몇 번 걸렸는지 보고 `harness.config.json`을 조정합니다. 끄는 방법은 README의 [문제 해결](../README.md#문제-해결)에 있습니다.
