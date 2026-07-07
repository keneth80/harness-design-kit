# {{PROJECT_NAME}}

## 프로젝트 개요
- 도메인: {{DOMAIN}}
- 생성일: {{DATE}}

## CONTEXT.md

프로젝트의 도메인 용어 사전은 `CONTEXT.md`에 정의한다.
새로운 도메인 용어가 등장하면 반드시 CONTEXT.md에 추가할 것.
의사결정 기록은 `docs/adr/`에 ADR(Architecture Decision Record)로 남긴다.

## 코딩 규칙

AI 코딩의 흔한 실수를 줄이기 위한 전역 지침. 신중함 > 속도(사소한 작업은 예외).
스택별(프론트/백엔드) 규칙은 각 dev 에이전트가 따로 가진다.

### 1. 구현 전 사고
- 가정은 명시하고, 불확실하면 묻는다. 해석이 갈리면 임의로 고르지 말고 대안을 제시한다.
- 더 간단한 방법이 있으면 제안한다. 혼란스러우면 멈추고 무엇이 불분명한지 묻는다.

### 2. 단순성 우선
- 문제를 푸는 최소 코드만. 요청 안 한 기능·추상화·유연성·예외처리 추가 금지.
- 200줄로 쓸 걸 50줄로 줄일 수 있으면 다시 쓴다. "시니어가 과하다고 할까?" → 그렇다면 단순화.

### 3. 외과적 변경
- 요청과 직접 연결된 라인만 바꾼다. 인접 코드·주석·포맷을 임의로 "개선"하지 않는다.
- 본인 변경이 만든 미사용 코드만 정리. 기존 죽은 코드는 언급만 하고 둔다.

### 4. 목표 기반 실행
- 명령을 검증 가능한 목표로 바꾼다. "고쳐줘" → "재현 테스트 작성 후 통과시킨다".
- 다단계는 짧은 계획 + 단계별 검증 체크포인트를 제시한다.

### 5. 네이밍
- 이름은 의도를 드러낸다. 함수=동작, 변수=의미.
- Boolean은 is/has/can/should, 이벤트 핸들러는 handle, React hook은 use로 시작.
- data/temp/result 같은 모호한 이름은 좁은 범위에서만.

### 6. 주석
- "무엇"이 아니라 "왜"를 적는다. 코드로 자명한 건 주석 금지.
- 비즈니스 규칙·보안 판단·우회 처리·외부 API 제한·호환성 이슈·예외 처리 이유엔 주석을 단다.
- 임시 코드는 TODO/FIXME 표기.

### 7. 변경 승인 (사전 보고 필수)
다음은 임의로 하지 말고 먼저 보고·승인받는다:
- 패키지 설치, 아키텍처/스키마/public API 변경, 인증·인가 변경, 배포·환경변수 변경,
  보안 로직 변경, 대규모 파일 이동·포맷팅·리팩토링.

### 8. 보안
- 키·토큰·비밀번호·시크릿을 코드에 직접 쓰지 않는다. 실제 개인정보를 예시 데이터로 쓰지 않는다.
- 환경변수는 .env.example이나 문서로만 안내.

### 9. 구현 후 보고
작업을 마치면 짧게 보고: 변경한 파일 / 주요 변경 / 단순화한 부분 / 알려진 한계 / 다음 추천 작업.

## 하네스 프로파일 (lite / full)

이 프로젝트의 하네스는 두 프로파일로 운영된다. 현재 프로파일은 `harness.config.json`의 `profile` 필드 참조.
- **lite (기본)**: drift_guard(완화 모드 지원) + verify_guard + security_gate + secret_scan + codemap 훅만 상시 발동.
  코드 리뷰는 자동 발동하지 않으며 `/verify`로 온디맨드 실행한다.
- **full**: 위 + back-pressure(Stop), 자동 code_reviewer(PostToolUse), 리포트 생성, 풀 사이클 커맨드/에이전트.
- 전환: `bash .claude/profiles/switch.sh <lite|full>`
- drift_guard 완화: `harness.config.json`의 `drift_guard.mode`(block/warn/off)와 `warn_paths`(glob)로 제어.
  `warn_paths`에 걸리는 경로(예: `frontend/**`)는 차단 대신 경고만 한다.

## Back-pressure (자기 검증) — full 프로파일 전용

full 프로파일에서는 작업 완료 시 Stop Hook이 자동으로 타입체크/린트/테스트를 실행한다.
실패하면 exit 2를 반환하여 에이전트가 에러를 수정할 때까지 재작업한다.
성공하면 완전히 침묵한다 (컨텍스트에 아무것도 추가하지 않음).
lite 프로파일에서는 verify_guard 경고와 온디맨드 `/verify`로 대신한다.

## 디렉토리 구조

- `src/` — 소스 코드
- `tests/` — 테스트
- `docs/adr/` — Architecture Decision Records
- `CONTEXT.md` — 도메인 용어 사전
- `PROGRESS.md` — 작업 진행 상황 (`/checkpoint`로 업데이트). 새 세션 시작 시 반드시 먼저 읽을 것
- `.claude/` — 하네스 (skills, hooks, commands, rules)

상세 구조는 `Glob`으로 탐색할 것.

## 코드맵 (codemap.md)

`docs/codemap.md`는 각 파일이 무엇을 export하고 어떤 로컬 모듈을 import하는지 자동 생성한 지도다.
세션이 끊겨도 전체 코드를 다 읽지 않고 구조를 빠르게 파악하기 위한 것이다.

- **세션 시작 시 자동 로드**된다(SessionStart 훅). 새 세션에서 코드 구조를 파악할 때 먼저 참고할 것.
- **작업 종료 시 자동 갱신**된다(Stop 훅). 코드를 수정하면 작업 끝에 코드맵이 최신으로 박제된다.
- 수동 갱신: `python3 .claude/hooks/codemap.py`
- **직접 수정하지 말 것** — 자동 생성물이다. 함수 본문의 호출관계나 의미는 담지 않으니 세부는 실제 코드를 볼 것.

## 슬래시 커맨드

`/명령어`로 직접 호출하는 단축 명령. 자주 쓰는 작업과 워크플로우 단계를 묶어둔 것이다.

**lite 프로파일 (기본)**
- `/verify` — code-verifier로 변경 코드를 다층 검증 + 변경 diff 코드 리뷰(온디맨드).
- `/security-review` — security-reviewer(opus)로 논리적 취약점(권한 누락, IDOR, Supabase RLS) 점검. 기능 완료 후·배포 전 권장.
- `/dev-start` — 현재 상태 파악 후 다음 작업 제안.
- `/lessons` — 학습된 교훈·최근 에러 기록 조회.

**full 프로파일 전용** (`bash .claude/profiles/switch.sh full`로 활성화)
- 설계·기획: `/grill`, `/plan-start`, `/architect`, `/ui-design`
- 구현·테스트: `/tdd`, `/test-cases`, `/diagnose`
- 검증·리포트: `/qa-boundary`, `/verify-report`, `/monitor`

**은퇴된 커맨드** — 공식 플러그인으로 대체
- `/commit` → **commit-commands** 플러그인
- `/pr-review` → **pr-review-toolkit** 플러그인

> 참고: 구현·테스트·검증 커맨드는 해당 에이전트(qa-tester, code-verifier 등)를 호출한다.
> Codex 분업(design-codex) 환경에는 설계 단계 커맨드만 포함된다.
