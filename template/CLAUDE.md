# JARVIS Browser Chatbot

JARVIS Home AI OS의 브라우저 자동화 에이전트를 실행하는 웹 챗봇 애플리케이션.
가족 구성원이 웹 UI에서 자연어로 브라우저 자동화 작업을 요청하고, 실시간으로 진행 상황을 확인한다.

## 핵심 유스케이스

1. 웹 챗봇에서 "구글시트에서 OOO 찾아서 메타 비즈니스 답장해줘" 입력
2. 백엔드 LangGraph Router가 의도 파악 → 서비스 식별 → 브라우저 자동화 실행
3. 실시간 WebSocket으로 진행 상황 스트리밍 (스크린샷 포함)
4. 완료 시 결과를 챗봇에 표시 + Telegram 알림 발송

## 기술 스택

### Frontend (웹 챗봇)
- Next.js 15 (App Router)
- React 19 + TypeScript
- Tailwind CSS 4
- WebSocket (실시간 메시지 스트리밍)
- next-auth (가족 멀티유저 인증)

### Backend (자동화 엔진)
- Python 3.12, FastAPI (WebSocket + REST)
- LangGraph (StateGraph 기반 파이프라인)
- Playwright (CDP 연결, 브라우저 자동화)
- Browser Use (AI 브라우저 에이전트)
- LM Studio (localhost:1234, OpenAI 호환 API)
- python-telegram-bot v20+ (알림 전용)
- structlog (JSON 로깅)

## 아키텍처

```
┌──────────────┐     WebSocket      ┌──────────────────┐
│  Next.js UI  │◄──────────────────►│   FastAPI Server  │
│  (챗봇 웹)   │     REST API       │                  │
│              │◄──────────────────►│  LangGraph Router │
└──────────────┘                    │       │          │
                                    │       ▼          │
                                    │  BrowserManager  │
                                    │   ┌────┬────┐   │
                                    │   │9222│9223│   │  Telegram
                                    │   │Ggl │Meta│   │──► 알림
                                    │   └────┴────┘   │
                                    └──────────────────┘
```

### 멀티 Chrome 인스턴스

| 포트 | 프로필 | 서비스 | CDP 연결 |
|------|--------|--------|----------|
| 9222 | ~/chrome-profiles/google | Google Sheets, Gmail, Drive | `--remote-debugging-port=9222 --user-data-dir=...` |
| 9223 | ~/chrome-profiles/meta | Meta Business Suite | `--remote-debugging-port=9223 --user-data-dir=...` |
| 9224 | ~/chrome-profiles/general | Naver, Coupang 등 | `--remote-debugging-port=9224 --user-data-dir=...` |

### 파이프라인 흐름

```
웹 챗봇 메시지 (WebSocket)
  → FastAPI → LangGraph Router (의도 파악, 서비스 식별)
    → BrowserManager (해당 포트 Chrome에 CDP 연결)
      → CDP 초기화 (다운로드/권한/다이얼로그)
        → Task 실행 (Sheets 읽기, Meta 메시지 전송 등)
          → 실시간 상태 스트리밍 (WebSocket)
            → 완료 결과 → 챗봇 응답 + Telegram 알림
```

## 의사결정 이력

| 결정 | 선택 | 사유 |
|------|------|------|
| 브라우저 연결 | CDP (`--remote-debugging-port`) | 기존 인증 세션 재사용, 프로필 잠금 충돌 방지 |
| 프론트엔드 | Next.js 15 App Router | SSR, 라우팅, 인증 통합 |
| 실시간 통신 | WebSocket (FastAPI native) | 양방향 스트리밍 필수 |
| 인증 | next-auth + 가족 계정 | 멀티유저, 각자 다른 에이전트 프로필 |
| 로컬 LLM | LM Studio (localhost:1234) | OpenAI 호환, 비용 $0 |
| Telegram | 알림 전용 | 웹 챗봇이 메인 인터페이스 |
| `launch_persistent_context` | ❌ 제외 | 프로필 잠금 충돌 |
| Qwen3-8B tool calling | ❌ 불안정 (50-70%) | 브라우저 자동화에 부적합 |

## 디렉토리 구조

- `CONTEXT.md` — 도메인 용어 사전
- `docs/adr/` — Architecture Decision Records
- `src/` — Next.js 15 Frontend (App Router, components, hooks, types)
- `backend/` — Python FastAPI 서버 (core, agents, tasks, router, websocket, telegram)
- `backend/config/` — browsers.yaml (Chrome 인스턴스), services.yaml (서비스 매핑)
- `tests/` — unit, integration, e2e
- `.claude/` — 하네스 (agents, skills, hooks, commands, rules)

상세 구조는 `Glob`으로 탐색할 것.

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

## 핵심 제약사항

1. Chrome 136+: `--remote-debugging-port`에 `--user-data-dir` 필수 동반
2. CDP 연결 시 초기화 필수: `Browser.setDownloadBehavior`, `Browser.setPermission`
3. Playwright CDP 연결: `connect_over_cdp("http://localhost:{port}")` 사용
4. WebSocket 메시지 포맷: `{ type, payload, userId, timestamp }` 통일
5. LM Studio API: `http://localhost:1234/v1/chat/completions` (OpenAI 호환)
6. 가족별 동시 접속 지원 — WebSocket 세션은 userId 기준으로 분리

## Back-pressure (자기 검증)

작업 완료 시 Stop Hook이 자동으로 타입체크/린트/테스트를 실행한다.
실패하면 exit 2를 반환하여 에이전트가 에러를 수정할 때까지 재작업한다.
성공하면 완전히 침묵한다 (컨텍스트에 아무것도 추가하지 않음).

자동 감지하는 체크:
- `tsconfig.json` 존재 → `tsc --noEmit`
- `package.json`에 lint 스크립트 → `npm run lint`
- `tests/` 하위에 `test_*.py` 존재 → `pytest -x -q`
- `vitest.config.ts` 존재 → `vitest run`
- `PROGRESS.md` — 작업 진행 상황 (`/checkpoint`로 업데이트). 새 세션 시작 시 반드시 먼저 읽을 것

## 코드맵 (codemap.md)

`docs/codemap.md`는 각 파일이 무엇을 export하고 어떤 로컬 모듈을 import하는지 자동 생성한 지도다.
세션이 끊겨도 전체 코드를 다 읽지 않고 구조를 빠르게 파악하기 위한 것이다.

- **세션 시작 시 자동 로드**된다(SessionStart 훅). 새 세션에서 코드 구조를 파악할 때 먼저 참고할 것.
- **작업 종료 시 자동 갱신**된다(Stop 훅). 코드를 수정하면 작업 끝에 코드맵이 최신으로 박제된다.
- 수동 갱신: `python3 .claude/hooks/codemap.py`
- **직접 수정하지 말 것** — 자동 생성물이다. 함수 본문의 호출관계나 의미는 담지 않으니 세부는 실제 코드를 볼 것.

## 슬래시 커맨드

`/명령어`로 직접 호출하는 단축 명령. 자주 쓰는 작업과 워크플로우 단계를 묶어둔 것이다.

**설계·기획 단계**
- `/grill` — 코딩 전 요구사항을 질문 공세로 명확히 한다(정렬 불일치 방지).
- `/plan-start` — 기획 시작. goal/prd를 읽고 ui-planner로 요구사항을 정리.
- `/architect` — 빌드 설정·도메인 엔티티·공유 타입 스캐폴딩 생성(dev 직전).
- `/ui-design` — UI 설계. ui-designer로 mockup·ui-spec 작성.

**구현·테스트 단계**
- `/tdd` — 기능을 TDD(RED→GREEN→리팩토링)로 구현.
- `/test-cases` — qa-tester로 테스트 케이스 작성.
- `/diagnose` — 버그를 재현→최소화→원인규명으로 진단(추측 수정 금지).

**검증 단계**
- `/verify` — code-verifier로 변경 코드를 test-cases 기준 다층 검증.
- `/qa-boundary` — qa-engineer로 모듈 간 경계(API↔타입, 화면↔API) 검증.
- `/verify-report` — 최신 검증 리포트를 열어 요약.
- `/pr-review` — 현재 브랜치 변경사항 리뷰(규칙·범위·품질).

**보조**
- `/commit` — 변경사항 분석 후 conventional commit 생성.
- `/dev-start` — 현재 상태 파악 후 다음 작업 제안.
- `/lessons` — 학습된 교훈·최근 에러 기록 조회.
- `/monitor` — 하네스 훅 동작 기록 요약(HARNESS_MONITOR=1 필요).

> 참고: 구현·테스트·검증 커맨드는 해당 에이전트(qa-tester, code-verifier 등)를 호출한다.
> Codex 분업(design-codex) 환경에는 설계 단계 커맨드만 포함된다.
