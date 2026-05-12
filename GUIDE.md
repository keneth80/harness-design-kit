# Claude Code 검증 하네스 — 설치 & 실행 가이드

## 1. 전체 구조 이해

```
scaffold.sh 실행 → 프로젝트 폴더 생성
                      │
                      ▼
my-project/
├── CLAUDE.md                          ⬅ Claude Code가 자동 로드하는 프로젝트 컨텍스트
├── .gitignore
├── src/                               ⬅ 소스 코드 작성 위치
├── tests/                             ⬅ 테스트 코드
│
└── .claude/                           ⬅ Claude Code 설정 디렉토리 (핵심)
    ├── settings.json                  ⬅ Hook 설정 — 어떤 이벤트에 어떤 스크립트 실행할지
    │
    ├── hooks/                         ⬅ 검증 스크립트 3종 (자동 실행됨)
    │   ├── security_gate.py           │  PreToolUse  → Bash 명령 실행 전 위험 차단
    │   ├── code_reviewer.py           │  PostToolUse → 파일 수정 후 AI 코드 리뷰
    │   └── report_generator.py        │  Stop        → 세션 종료 시 HTML 리포트 생성
    │
    ├── verifier-scripts/              ⬅ Hook들이 공유하는 유틸리티
    │   └── llm_client.py              │  LM Studio OpenAI 호환 API 클라이언트
    │
    ├── agents/                        ⬅ 서브에이전트 정의
    │   └── code-verifier.md           │  심층 검증용 (Read/Grep/Glob 도구 사용)
    │
    ├── skills/                        ⬅ Harness 플러그인이 생성하는 스킬 위치
    │   └── (harness가 자동 생성)
    │
    ├── commands/                      ⬅ 슬래시 커맨드
    │   ├── verify-report.md           │  /verify-report → 리포트 요약
    │   └── verify-status.md           │  /verify-status → 시스템 상태 점검
    │
    └── reports/                       ⬅ 검증 대시보드 HTML 출력
        └── latest.html → (심볼릭 링크)
```


## 2. 검증 파이프라인 동작 흐름

```
당신이 Claude Code에서 작업 중...

┌─────────────────────────────────────────────────────────────┐
│  "이 파일 수정해줘" 또는 "이 스크립트 실행해줘"              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
         ┌─── Bash 명령인가? ───┐
         │ YES                  │ NO
         ▼                      │
  security_gate.py              │
  (regex 패턴 매칭)             │
  ┌──────────┐                  │
  │ rm -rf / │→ 🛑 차단         │
  │ chmod 777│→ 🛑 차단         │
  │ ls -la   │→ ✅ 통과         │
  └──────────┘                  │
         │                      │
         ▼                      ▼
    Claude가 도구 실행 (Write/Edit/Bash)
                       │
                       ▼
         ┌─── 파일 수정인가? ───┐
         │ YES                  │ NO
         ▼                      │
  code_reviewer.py              │
  ┌────────────────────┐        │
  │ Phase 1: 정적 분석 │        │
  │  - API 키 노출?    │        │
  │  - eval() 사용?    │        │
  │  - SQL injection?  │        │
  │                    │        │
  │ CRITICAL → 🛑 즉시 │        │
  │                    │        │
  │ Phase 2: AI 리뷰   │        │
  │  (LM Studio 로컬)  │        │
  │  - 보안 심층 분석   │        │
  │  - 성능 패턴 검사   │        │
  │  - 코드 맥락 평가   │        │
  │                    │        │
  │ should_block?      │        │
  │  true → 🛑 차단     │        │
  │  false → ✅ 통과    │        │
  └────────────────────┘        │
         │                      │
         ▼                      ▼
    결과를 audit.jsonl에 기록
                       │
                       ▼
    세션 종료 ("exit" 또는 Ctrl+C)
                       │
                       ▼
  report_generator.py (백그라운드)
  ┌────────────────────────────┐
  │ audit.jsonl 분석            │
  │ → HTML 대시보드 생성        │
  │ → .claude/reports/latest.html │
  └────────────────────────────┘
```


## 3. 설치 (3단계)

### Step 1: scaffold.sh 다운로드 & 실행

```bash
# scaffold.sh를 원하는 위치에 다운로드 후:
bash scaffold.sh my-project webapp

# 또는 도메인 지정:
bash scaffold.sh jarvis-browser automation
bash scaffold.sh my-api api
bash scaffold.sh side-project        # 기본(general)
```

### Step 2: LM Studio 서버 준비 (선택사항)

```bash
# LM Studio가 없거나 서버가 꺼져있으면 정적 분석만 동작 (문제 없음)
# AI 리뷰까지 원하면:

# 1. LM Studio 실행
# 2. 원하는 모델 로드 (예: qwen3-8b, GLM-4.7-9B 등)
# 3. Local Server 탭 > Start Server (기본 포트 1234)

# 모델명 확인:
curl -s http://localhost:1234/v1/models | python3 -m json.tool

# 모델명 변경하고 싶으면:
#   .claude/verifier-scripts/llm_client.py 에서
#   DEFAULT_MODEL = "qwen3-8b" 부분을 LM Studio에 로드한 모델명으로 변경
#   (단일 모델만 로드했으면 아무 값이나 넣어도 동작)
#
# 포트 변경 시:
#   LMSTUDIO_BASE_URL = "http://localhost:1234" 부분 수정
```

### Step 3: Claude Code 시작

```bash
cd my-project
claude
```

이 시점에서 벌써 검증이 작동합니다. Claude Code가 `.claude/settings.json`을 자동으로 읽고 Hook을 등록합니다.


## 4. Harness 적용 (에이전트 팀 구성)

검증 하네스 위에 revfactory/harness를 올려서 도메인 특화 에이전트 팀을 생성합니다.

```bash
# Claude Code 안에서:

# 1. Harness 플러그인 설치
/plugin marketplace add revfactory/harness
/plugin install harness@harness

# 2. 하네스 구성 요청
> 하네스 구성해줘
# 또는
> Build a harness for this project. 웹 애플리케이션 개발용으로
#   React + FastAPI 스택, 인증/결제/관리자 기능 포함.
```

Harness가 `.claude/agents/`와 `.claude/skills/`에 파일을 생성합니다.
6가지 아키텍처 패턴 중 프로젝트에 맞는 것을 자동 선택:

| 패턴 | 용도 |
|------|------|
| Pipeline | 순차 처리 (기획→개발→테스트→배포) |
| Fan-out/Fan-in | 병렬 작업 후 합치기 |
| Expert Pool | 전문가 에이전트 풀에서 적합한 에이전트 선택 |
| Producer-Reviewer | 생성→검증 반복 |
| Supervisor | 감독자가 하위 에이전트 조율 |
| Hierarchical | 계층적 위임 |

생성 후 프로젝트 구조:

```
.claude/
├── settings.json          ← Hook (검증)
├── hooks/                 ← 검증 스크립트
├── verifier-scripts/
├── agents/
│   ├── code-verifier.md   ← 검증 에이전트 (scaffold가 생성)
│   ├── frontend-dev.md    ← 프론트엔드 에이전트 (harness가 생성)
│   ├── backend-dev.md     ← 백엔드 에이전트 (harness가 생성)
│   └── qa-tester.md       ← QA 에이전트 (harness가 생성)
├── skills/
│   └── harness/
│       └── ...            ← 도메인 스킬 (harness가 생성)
├── commands/
│   ├── verify-report.md
│   └── verify-status.md
└── reports/
```


## 5. 실제 사용 시나리오

### 시나리오 A: 정상 개발 흐름

```
You: 사용자 로그인 API를 만들어줘

Claude: (Write 도구로 src/auth/login.py 생성)
        ↓
        code_reviewer.py 자동 실행
        ├─ 정적: 시크릿 없음 ✅
        └─ AI: 보안 OK, 성능 OK, 맥락 OK ✅
        ↓
        파일 생성 완료!

You: exit
        ↓
        report_generator.py 자동 실행 (백그라운드)
        → .claude/reports/latest.html 생성

You: (브라우저에서 리포트 확인)
```

### 시나리오 B: 위험 감지 & 차단

```
You: DB를 초기화하는 스크립트 실행해줘

Claude: (Bash 도구로 "DROP TABLE users" 실행 시도)
        ↓
        security_gate.py 자동 실행
        🛑 차단: "DB 삭제 명령"
        ↓
Claude: "보안 게이트가 이 명령을 차단했습니다.
         DROP TABLE은 직접 실행할 수 없습니다.
         마이그레이션 스크립트를 통해 안전하게 처리할까요?"
```

### 시나리오 C: AI가 시크릿 하드코딩 시도

```
Claude: (Edit 도구로 config.py에 API_KEY = "sk-abc123..." 추가 시도)
        ↓
        code_reviewer.py 자동 실행
        Phase 1 정적: 🔴 CRITICAL: OpenAI API키 하드코딩
        🛑 즉시 차단 (LLM 호출 안 함)
        ↓
Claude: "코드 검증에서 차단되었습니다.
         API 키를 환경변수로 변경하겠습니다."
        ↓
        (Edit로 os.environ.get("OPENAI_API_KEY") 변경)
        ↓
        code_reviewer.py: 정적 ✅, AI ✅ → 통과
```


## 6. 커스터마이징

### 검증 강도 조절

```python
# .claude/hooks/code_reviewer.py 에서

# AI 리뷰 프롬프트 수정 (REVIEW_SYSTEM 변수)
# → "should_block=true 기준을 medium 이상으로 변경" 등

# 정적 분석 패턴 추가
SECRET_PATTERNS = [
    # 기존 패턴...
    (r'AKIA[0-9A-Z]{16}', "AWS Access Key"),  # ← 추가
]
```

### 특정 파일/폴더 스킵

```python
# code_reviewer.py의 SKIP_PATTERNS에 추가
SKIP_PATTERNS = [
    # 기존...
    "migrations/",    # DB 마이그레이션은 스킵
    "fixtures/",      # 테스트 데이터 스킵
]
```

### 모델 교체

```python
# .claude/verifier-scripts/llm_client.py

# 모델명은 LM Studio에서 로드한 모델의 identifier
# Local Server 탭 또는 curl http://localhost:1234/v1/models 로 확인
DEFAULT_MODEL = "qwen3-8b"        # 기본값 (LM Studio 로드 모델명)

# 포트 변경 시:
LMSTUDIO_BASE_URL = "http://localhost:1234"  # LM Studio 기본 포트
# LMSTUDIO_BASE_URL = "http://localhost:8080"  # 커스텀 포트
```

### Telegram 알림 연동 (JARVIS용)

```python
# report_generator.py main() 끝에 추가:
import requests
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
if TELEGRAM_BOT_TOKEN and stats["blocked"] > 0:
    msg = f"🛑 검증 리포트: {stats['blocked']}건 차단, {stats['passed']}건 통과"
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    )
```


## 7. 새 프로젝트 시작 체크리스트

```
□ bash scaffold.sh <이름> <도메인>
□ cd <이름>
□ LM Studio에서 모델 로드 & 서버 시작 (선택)
□ claude
□ /plugin marketplace add revfactory/harness
□ /plugin install harness@harness
□ "하네스 구성해줘"
□ CLAUDE.md에 기술 스택/아키텍처 업데이트
□ 개발 시작 → Hook이 알아서 검증
□ /verify-status 로 시스템 상태 확인
□ 세션 종료 후 .claude/reports/latest.html 확인
```
