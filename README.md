# JARVIS Harness Kit

Claude Code 하네스 엔지니어링이 적용된 프로젝트 템플릿 킷.
`scaffold.sh`를 실행하면 완성된 하네스(에이전트 팀 + 스킬 + 검증 Hook + 슬래시 커맨드)가 포함된 프로젝트를 생성합니다.

---

## 킷 구조

```
jarvis-harness-kit/
├── scaffold.sh        ← 프로젝트 생성기
├── README.md          ← 이 파일
├── GUIDE.md           ← 상세 가이드 (검증 파이프라인, 커스터마이징)
└── template/          ← 하네스 템플릿 원본 (scaffold가 복사함)
    ├── CLAUDE.md                 아키텍처 청사진
    ├── .claude/
    │   ├── agents/    (4개)      frontend-dev, backend-dev, qa-tester, code-verifier
    │   ├── skills/    (4개)      browser-automation, chatbot-ui, task-routing, orchestrator
    │   ├── hooks/     (4개)      security_gate, code_reviewer, backpressure, report_generator
    │   ├── commands/  (3개)      /dev-start, /browser-status, /verify-report
    │   ├── rules/     (2개)      ws-protocol, cdp-init
    │   └── settings.json         Hook 설정
    ├── src/                      Next.js 15 프론트엔드
    ├── backend/                  FastAPI + LangGraph + Playwright
    └── .env.example
```

---

## 실행 가이드

### Step 1: 프로젝트 생성

```bash
cd jarvis-harness-kit
bash scaffold.sh <프로젝트명> [도메인]

# 예시
bash scaffold.sh jarvis-browser-chatbot webapp
```

대화형 프롬프트에서 3가지를 선택합니다:

| 항목 | 선택지 | 기본값 |
|------|--------|--------|
| DB | Supabase 로컬, Supabase 클라우드, PostgreSQL, SQLite, 없음 | 없음 |
| 모니터링 | agents-observe, Hook 로깅, 없음 | Hook 로깅 |
| 로컬 LLM | LM Studio, Ollama, 없음 | LM Studio |

### Step 2: 프로젝트 폴더로 이동

```bash
cd <프로젝트명>
```

### Step 3: 인프라 실행 (선택한 항목에 따라)

```bash
# Supabase 로컬을 선택한 경우
cd supabase && docker compose up -d && cd ..

# LM Studio를 선택한 경우
# → LM Studio 앱에서 모델 로드 후 Local Server > Start Server (포트 1234)

# Chrome 인스턴스 실행 (브라우저 자동화용)
chmod +x backend/scripts/launch-chrome.sh
./backend/scripts/launch-chrome.sh start

# 처음 실행 시 각 브라우저에서 로그인 필요:
#   포트 9222 브라우저 → Google 계정 로그인
#   포트 9223 브라우저 → Meta/Facebook 계정 로그인
#   포트 9224 브라우저 → 기타 서비스 로그인
```

### Step 4: Claude Code 시작

```bash
claude
```

CLAUDE.md가 자동으로 로드되어 프로젝트 전체 맥락(아키텍처, 기술 스택, 코딩 규칙, 제약사항)을 파악한 상태로 시작합니다.

### Step 5: 첫 번째 명령

```
/dev-start
```

프로젝트 현황을 분석하고 다음 작업을 우선순위별로 제안합니다.

### Step 6: 순차 개발

`/dev-start`의 제안을 따르거나, 아래 순서로 진행합니다:

```
> BrowserManager 코어 모듈 구현해줘
> FastAPI WebSocket 엔드포인트 구현해줘
> LangGraph 라우터 구현해줘
> 챗봇 메인 페이지 UI 구현해줘
> Google Sheets 태스크 구현해줘
> Meta Business 태스크 구현해줘
> Telegram 알림 모듈 구현해줘
```

모든 코드 수정마다 검증 Hook이 자동으로 실행됩니다:
- `security_gate.py` → 위험 명령 차단 (PreToolUse)
- `code_reviewer.py` → 정적 분석 + AI 코드 리뷰 (PostToolUse)
- `backpressure.py` → 타입체크/린트/테스트 실행, 실패 시 에이전트 재작업 강제 (Stop)
- `report_generator.py` → 세션 종료 시 HTML 대시보드 생성 (Stop, async)

---

## 슬래시 커맨드

| 커맨드 | 설명 |
|--------|------|
| `/dev-start` | 프로젝트 현황 분석 + 다음 작업 제안 |
| `/browser-status` | Chrome 인스턴스 연결 상태 + LM Studio 상태 확인 |
| `/verify-report` | 최신 검증 대시보드 요약 |
| `/observe-setup` | agents-observe 모니터링 설치 가이드 (선택 시) |

---

## 하네스 확장 (선택)

revfactory/harness 플러그인으로 에이전트 팀을 더 정교하게 구성할 수 있습니다:

```
/plugin marketplace add revfactory/harness
/plugin install harness@harness
> 하네스 구성해줘
```

---

## 검증 대시보드

세션 종료 시 `.claude/reports/latest.html`에 자동 생성됩니다.
브라우저에서 열면 통과율, 차단 내역, AI 검증 이슈를 한눈에 볼 수 있습니다.

```bash
open .claude/reports/latest.html
```

---

## 새 프로젝트 만들기

template/은 항상 원본으로 남아있으므로, 다른 프로젝트도 같은 하네스 기반으로 생성 가능합니다:

```bash
cd jarvis-harness-kit
bash scaffold.sh video-factory automation
bash scaffold.sh my-api api
bash scaffold.sh side-project general
```
