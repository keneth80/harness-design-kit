# JARVIS Production Chatbot - 완전 구현 프로젝트

## 🎯 프로젝트 목표
지금까지 만든 하네스 기반 자산(jarvis-harness-kit, HI-ZARVIS MCP 패턴)을 활용해
**production-ready JARVIS 챗봇**을 완성한다. 최종 산출물은 다른 컴퓨터에서도 
바로 실행 가능한 **단일 실행 파일(executable)**.

## 📋 핵심 요구사항

### 1. 아키텍처
- **LLM Backend**: LM Studio (localhost:1234) + Gemma 3 4B 또는 Gemma 3 1B (라이트 모델 우선)
- **Agent Framework**: LangGraph (supervisor + worker 패턴, 기존 JARVIS 구조 재사용)
- **UI**: Telegram Bot (python-telegram-bot)
- **Monitoring**: FastAPI + SSE 기반 실시간 대시보드 (포트 3800, HI-ZARVIS 패턴 차용)
- **RAG**: ChromaDB (local) + sentence-transformers (한국어: jhgan/ko-sroberta-multitask)
- **Context Memory**: 
  - Short-term: LangGraph InMemorySaver (세션 내 대화)
  - Long-term: SQLite + ChromaDB (영구 저장 + 의미 검색)
- **Packaging**: PyInstaller (--onefile) 또는 Nuitka

### 2. 디렉토리 구조
```
jarvis-v2/
├── src/
│   ├── core/
│   │   ├── llm.py              # LM Studio 클라이언트 (OpenAI 호환)
│   │   ├── config.py           # 환경설정 (pydantic-settings)
│   │   └── logger.py           # 구조화 로깅 (loguru)
│   ├── agents/
│   │   ├── supervisor.py       # LangGraph 라우터
│   │   ├── chat_agent.py       # 일반 대화
│   │   ├── rag_agent.py        # RAG 기반 답변
│   │   └── tools.py            # 공용 도구
│   ├── memory/
│   │   ├── short_term.py       # 세션 컨텍스트 (last N turns)
│   │   ├── long_term.py        # SQLite 대화 영속화
│   │   └── rag_store.py        # ChromaDB RAG 벡터 저장소
│   ├── telegram/
│   │   ├── bot.py              # Telegram 핸들러
│   │   └── handlers.py         # /start, /reset, /ingest 등
│   ├── dashboard/
│   │   ├── server.py           # FastAPI + SSE
│   │   ├── events.py           # 이벤트 버스 (asyncio.Queue)
│   │   └── static/             # HTML 대시보드 (단일 파일)
│   └── main.py                 # 진입점 (telegram + dashboard 동시 실행)
├── data/
│   ├── conversations.db        # SQLite
│   ├── chroma/                 # ChromaDB persist
│   └── documents/              # RAG 원본 문서 (.md, .pdf, .txt)
├── .env.example
├── requirements.txt
├── build.py                    # PyInstaller 빌드 스크립트
└── README.md
```

### 3. 컴포넌트 상세 스펙

#### LLM Backend (`src/core/llm.py`)
```python
# LM Studio는 OpenAI 호환 API 제공
# - base_url: http://localhost:1234/v1
# - model: "gemma-3-4b-it" (또는 설정값)
# - openai SDK 사용, async 지원 필수
# - tool_calling 불안정성 고려해 JSON 모드 fallback 구현
```

#### LangGraph Supervisor (`src/agents/supervisor.py`)
```
START → supervisor (라우팅 판단)
        ├→ chat_agent (일반 대화)
        ├→ rag_agent (지식 검색 필요시)
        └→ END
        
- State: messages, user_id, session_id, retrieved_docs, route
- Checkpointer: InMemorySaver (세션) + 종료 시 SQLite로 flush
- 모든 노드 진입/종료 시 dashboard event bus로 publish
```

#### RAG (`src/memory/rag_store.py`)
```
- ChromaDB PersistentClient (./data/chroma)
- Embedding: jhgan/ko-sroberta-multitask (한국어 최적화)
- Chunking: RecursiveCharacterTextSplitter (chunk=500, overlap=50)
- /ingest <파일경로> 텔레그램 명령으로 문서 추가
- top_k=3, score threshold 적용
```

#### Context Memory
```
Short-term (in-memory):
- 최근 10턴 대화를 system prompt 뒤에 주입
- LangGraph state에 포함

Long-term (SQLite):
스키마:
  conversations(id, user_id, session_id, role, content, ts, metadata_json)
  sessions(id, user_id, started_at, last_active_at, summary)
  
- 세션 종료 또는 일정 턴 이후 요약 생성 → sessions.summary 저장
- 새 세션 시작 시 직전 세션 요약을 컨텍스트로 주입
```

#### Telegram Bot (`src/telegram/bot.py`)
```
명령어:
  /start       - 세션 시작
  /reset       - 대화 컨텍스트 초기화 (새 세션)
  /history     - 최근 N턴 표시
  /ingest      - 답장 파일 RAG에 추가
  /status      - 대시보드 URL 안내
  /mode chat|rag - 라우팅 강제 지정
  
- 일반 메시지 → supervisor 호출
- typing action 표시
- 긴 응답 분할 전송 (4096자 제한)
```

#### 모니터링 대시보드 (`src/dashboard/`)
```
URL: http://localhost:3800

실시간 표시:
- 현재 활성 세션 수
- 최근 에이전트 실행 흐름 (supervisor→chat_agent 등)
- LLM 호출 통계 (호출 수, 평균 응답 시간, 토큰 추정치)
- RAG 검색 로그 (질의, 검색된 문서, 스코어)
- 최근 50개 이벤트 (SSE 스트림)
- 에러 로그 패널

기술:
- FastAPI + SSE (EventSource)
- 단일 HTML 파일 (Tailwind CDN, vanilla JS)
- asyncio.Queue 기반 이벤트 버스, 모든 agent 노드에서 publish
```

### 4. 하네스 기반 개발 워크플로우

기존 jarvis-harness-kit의 패턴을 적용:
- **agents/**: 각 에이전트는 독립 모듈, 명확한 입출력 계약
- **skills/**: 재사용 가능한 도구 (web_search, file_read 등은 향후 확장용 stub만)
- **hooks/**: PostToolUse 훅으로 dashboard 이벤트 자동 발행
- 모든 LLM 호출에 trace_id 부여, dashboard에서 추적 가능

### 5. 빌드 & 배포 (`build.py`)
```python
# PyInstaller --onefile
# 포함 자산: chroma 모델 파일, sentence-transformers 모델, static/
# hidden imports: chromadb, sentence_transformers, langgraph 관련
# 결과물: dist/jarvis.exe (Windows) / dist/jarvis (Mac/Linux)

# 실행 방식:
#   ./jarvis  →  .env 자동 로드, telegram bot + dashboard 동시 시작
#   사용자는 .env에 TELEGRAM_TOKEN, LM_STUDIO_URL만 채우면 됨
```

### 6. 환경변수 (`.env.example`)
```
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_IDS=     # 콤마구분, 비우면 모두 허용
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=gemma-3-4b-it
DASHBOARD_PORT=3800
DATA_DIR=./data
LOG_LEVEL=INFO
RAG_TOP_K=3
RAG_SCORE_THRESHOLD=0.3
CONTEXT_WINDOW_TURNS=10
```

## 🛠️ 구현 순서 (단계별)

**Phase 1: 기반 구축**
1. 프로젝트 구조 생성, `requirements.txt`, `.env.example`
2. `core/llm.py` - LM Studio 클라이언트 + 헬스체크
3. `core/config.py` - pydantic-settings 기반 설정
4. `core/logger.py` - loguru 설정

**Phase 2: 메모리 & RAG**
5. `memory/long_term.py` - SQLite 스키마 + CRUD
6. `memory/short_term.py` - 윈도우 기반 컨텍스트 빌더
7. `memory/rag_store.py` - ChromaDB ingest + query

**Phase 3: 에이전트**
8. `agents/tools.py` + `agents/chat_agent.py` + `agents/rag_agent.py`
9. `agents/supervisor.py` - LangGraph 그래프 빌드
10. 이벤트 버스 연동 (모든 노드에 trace 발행)

**Phase 4: UI & 대시보드**
11. `dashboard/server.py` + `events.py` + `static/index.html`
12. `telegram/bot.py` + `handlers.py`
13. `main.py` - asyncio.gather로 동시 실행

**Phase 5: 빌드**
14. `build.py` - PyInstaller spec
15. `README.md` - 설치 / 실행 / 빌드 가이드
16. 통합 테스트 (LM Studio 켜고 텔레그램 → 응답 → 대시보드 확인)

## ✅ 작업 시 준수사항

1. **점진적 구현**: Phase 단위로 끝낼 때마다 한 줄 요약 보고 후 다음 단계 진행
2. **타입 힌트 필수**: 모든 함수 시그니처에 type hint
3. **에러 처리**: LM Studio 미실행, Telegram 인증 실패, RAG 미구축 상황 graceful degrade
4. **로깅**: 모든 외부 호출(LLM, Telegram, ChromaDB)은 loguru로 trace_id와 함께 기록
5. **테스트 가능성**: 각 모듈은 독립 실행 가능한 `if __name__ == "__main__":` 블록 포함
6. **한국어 우선**: 시스템 프롬프트, 로그 메시지, 텔레그램 응답 모두 한국어
7. **메모리 효율**: Gemma 3 4B 기준 context 4K 토큰 내로 관리, 초과 시 자동 요약

## 🚀 시작 지시

지금부터 위 명세대로 Phase 1부터 순차 구현해줘.
각 Phase 완료 시:
- 생성/수정한 파일 목록
- 다음 Phase로 진행해도 되는지 확인 질문

먼저 Phase 1을 시작하면서 `requirements.txt`에 어떤 패키지를 넣을지 
명시하고 디렉토리 골격부터 만들어줘.