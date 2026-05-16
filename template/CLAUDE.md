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
LLM의 일반적인 코딩 실수를 줄이기 위한 행동 지침이다. 프로젝트별 지침이 있을 경우 본 가이드라인과 병합하여 사용한다.

트레이드오프: 본 지침은 속도보다 신중함에 우선순위를 둔다. 사소한 작업은 상황에 맞게 판단한다.

### 1. 구현 전 사고 (Think Before Coding)
가정하지 않는다. 모호함을 숨기지 않는다. 트레이드오프를 명확히 밝힌다.

구현을 시작하기 전 다음을 준수한다:

- 자신의 가정을 명시적으로 기술한다. 불확실한 경우 질문한다.

- 해석의 여지가 여러 가지라면 임의로 선택하지 말고 대안들을 제시한다.

- 더 간단한 접근 방식이 있다면 제안한다. 정당한 사유가 있다면 사용자의 요청에 반대 의견을 제시한다.

- 불분명한 부분이 있다면 작업을 중단한다. 혼란스러운 부분을 구체적으로 언급하며 질문한다.

### 2. 단순성 우선 (Simplicity First)
- 문제를 해결하는 최소한의 코드만 작성한다. 추측에 기반한 코드는 배제한다.

- 요청되지 않은 기능은 추가하지 않는다.

- 일회성 코드를 위해 추상화 계층을 만들지 않는다.

- 요청되지 않은 유연성이나 설정 가능성을 고려하지 않는다.

- 발생 불가능한 시나리오에 대한 예외 처리를 하지 않는다.

- 200줄의 코드를 50줄로 줄일 수 있다면 코드를 다시 작성한다.

- "시니어 엔지니어가 보기에 이 코드가 지나치게 복잡한가?"라고 자문한다. 그렇다면 단순화한다.

### 3. 정밀한 수정 (Surgical Changes)
필요한 부분만 수정한다. 본인이 만든 코드의 뒷정리만 수행한다.

기존 코드를 편집할 때 다음을 준수한다:

- 인접한 코드, 주석, 포맷을 임의로 개선하지 않는다.
- 망가지지 않은 부분을 리팩토링하지 않는다.
- 본인의 스타일과 다르더라도 기존 스타일을 따른다.
- 작업과 무관한 데드 코드를 발견하면 보고하되 직접 삭제하지 않는다.

수정으로 인해 사용되지 않게 된 요소가 발생할 경우:

- 본인의 수정으로 인해 불필요해진 임포트, 변수, 함수는 제거한다.
- 기존에 존재하던 데드 코드는 요청이 없는 한 그대로 둔다.
- 테스트 기준: 변경된 모든 라인은 사용자의 요청사항과 직접적으로 연결되어야 한다.

### 4. 목표 중심 실행 (Goal-Driven Execution)
성공 기준을 정의한다. 검증될 때까지 반복한다.
작업을 검증 가능한 목표로 변환한다:

- "유효성 검사 추가" → "잘못된 입력에 대한 테스트 작성 후 통과 확인"
- "버그 수정" → "버그를 재현하는 테스트 작성 후 통과 확인"
- "X 리팩토링" → "리팩토링 전후의 테스트 통과 확인"

다단계 작업의 경우 간략한 계획을 수립한다:

1. [단계] → 검증: [확인 사항]
2. [단계] → 검증: [확인 사항]
3. [단계] → 검증: [확인 사항]
성공 기준이 명확해야 독립적인 작업이 가능하다. "작동하게 만들기"와 같은 모호한 기준은 불필요한 재질의를 야기한다.

지침 작동 확인: Diff 내 불필요한 변경 감소, 복잡성으로 인한 재작성 빈도 감소, 구현 전 질문을 통한 명확한 의사결정 증대.

### 공통
- Grill first: 코딩 전에 `/grill`로 요구사항 정렬. 모든 분기가 해결될 때까지 코드를 쓰지 않는다
- TDD: vertical slice 단위. 테스트 1개 → 구현 → 테스트 1개 → 구현 반복. 테스트를 전부 먼저 쓰는 horizontal slicing 금지
- 테스트는 행위(behavior)를 검증. 내부 구현이 아닌 public interface를 통해 테스트
- 설계: 모듈은 깊게 만든다 — 간단한 인터페이스 뒤에 많은 기능을 숨긴다
- 시크릿: 환경변수 또는 .env — 하드코딩 절대 금지
- 에러 핸들링: 구체적 예외 타입 사용, bare except 금지
- 커밋: conventional commits (feat:, fix:, refactor:, test:, docs:)
- 도메인 용어: `CONTEXT.md`에 정의된 용어를 일관되게 사용. 새 용어는 즉시 추가
- 의사결정: 주요 기술적 결정은 `docs/adr/`에 ADR로 기록

### Frontend (TypeScript)
- strict 모드 필수
- 컴포넌트: function 선언 (arrow 아님), Props 타입 명시
- 상태: React 19 use() + Zustand (필요 시)
- 스타일: Tailwind utility-first, cn() 헬퍼 사용
- 파일 네이밍: PascalCase (컴포넌트), camelCase (유틸)

### Backend (Python)
- 타입 힌트 필수 (Python 3.12: `list[str]`, `dict[str, Any]`)
- async/await 기반 (모든 I/O)
- 로깅: structlog JSON 포맷
- CDP/Playwright 호출: 반드시 try-except + 재시도

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
