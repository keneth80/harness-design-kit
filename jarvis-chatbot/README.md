# JARVIS Chatbot

Telegram + LM Studio + LangGraph + ChromaDB로 구성된 개인 비서 챗봇.
실시간 모니터링 대시보드 포함. PyInstaller로 단일 실행파일로 패키징 가능.

## 아키텍처

```
Telegram ──► supervisor ──► chat_agent ──► LM Studio
                       └──► rag_agent ──► ChromaDB + jhgan/ko-sroberta-multitask
                                    │
                                    └──► LM Studio
                       │
                       └─ 이벤트 버스 ──► FastAPI/SSE 대시보드 (:3800)

SQLite ◄── 대화 영속화 (conversations.db)
```

| 컴포넌트 | 기술 |
|----------|------|
| LLM | LM Studio (OpenAI 호환, localhost:1234) |
| Agent | LangGraph (supervisor + chat/rag workers) |
| RAG | ChromaDB + sentence-transformers (`jhgan/ko-sroberta-multitask`) |
| Memory | SQLite (long-term) + InMemorySaver (short-term) |
| UI | python-telegram-bot |
| Dashboard | FastAPI + SSE + Tailwind |

## 빠른 시작

### 1) 사전 준비
- Python 3.12+ (3.14 검증됨)
- [LM Studio](https://lmstudio.ai) 실행 후 모델 로드 (예: `gemma-4-26b-a4b-it`)
- Telegram bot 토큰 ([@BotFather](https://t.me/BotFather))
- 본인 Telegram user ID ([@userinfobot](https://t.me/userinfobot))

### 2) 설치
```bash
python3 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env 편집 — TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, LMSTUDIO_MODEL 채우기
```

### 3) 실행
```bash
python -m src.main
```

- Telegram에서 봇에게 `/start` 전송
- 대시보드: http://localhost:3800

## .env 변수

| 키 | 기본값 | 설명 |
|----|--------|------|
| `TELEGRAM_BOT_TOKEN` | — | BotFather 발급 토큰 |
| `TELEGRAM_CHAT_ID` | (빈 값 → 모두 허용) | 허용 user ID, CSV |
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` | `/v1` 자동 보정 |
| `LMSTUDIO_MODEL` | `gemma-4-26b-a4b-it` | LM Studio에 로드된 모델 ID |
| `LMSTUDIO_API_KEY` | `lm-studio` | LM Studio는 검증 안 함 |
| `DASHBOARD_PORT` | `3800` | 대시보드 포트 |
| `DATA_DIR` | `./data` | SQLite, Chroma persist 디렉토리 |
| `LOG_LEVEL` | `INFO` | DEBUG/INFO/WARNING/ERROR |
| `RAG_TOP_K` | `3` | 검색 top_k |
| `RAG_SCORE_THRESHOLD` | `0.3` | cosine similarity 하한 |
| `CONTEXT_WINDOW_TURNS` | `10` | 단기 메모리 턴 수 |

## Telegram 명령어

| 명령 | 동작 |
|------|------|
| `/start` | 새 세션 시작 |
| `/reset` | 컨텍스트 초기화 + 새 세션 |
| `/history` | 최근 20개 메시지 |
| `/status` | 모델/RAG 문서 수/모드/대시보드 URL |
| `/mode chat\|rag\|auto` | 라우팅 강제 지정 |
| `/ingest <경로>` | 파일을 RAG에 추가 (또는 파일 첨부 + `/ingest`) |
| 그 외 메시지 | supervisor 호출 → 답변 |

## 모듈별 단독 실행 (스모크 테스트)

```bash
python -m src.core.config       # .env 로드 확인
python -m src.core.llm          # LM Studio healthcheck + chat
python -m src.memory.long_term  # SQLite CRUD
python -m src.memory.short_term # 컨텍스트 빌더
python -m src.memory.rag_store  # ChromaDB 임베딩/검색
python -m src.agents.supervisor # LangGraph end-to-end
python -m src.dashboard.server  # 대시보드 단독 실행
pytest tests/ -v                # 헬스체크 integration test
```

## 단일 실행파일 빌드

```bash
pip install pyinstaller
python build.py --clean
# 결과: dist/jarvis (Mac/Linux, ~263MB) 또는 dist/jarvis.exe (Windows)
./dist/jarvis    # 현재 cwd의 .env 사용, data/는 cwd/data
```

**배포 절차**
1. 대상 컴퓨터에 `dist/jarvis`와 `.env`를 같은 폴더로 복사
2. 그 폴더에서 `./jarvis` 실행
3. `data/` 디렉토리가 자동 생성되어 SQLite·ChromaDB가 보존됨

**중요 핀**
- `transformers<5.0` 필수. 5.x는 `_grouped_mm_can_dispatch`에서 `inspect.getsource`를 호출해 PyInstaller 번들과 충돌함 (이미 `requirements.txt`에 반영).
- sentence-transformers 가중치는 첫 실행 시 `~/.cache/huggingface`에 다운로드. 오프라인 배포는 모델 폴더를 `--add-data`로 포함.

**프로파일 경로 우선순위 (frozen 모드)**
1. `.env` 검색: cwd/.env → binary 옆/.env (cwd 우선)
2. `data_dir` 기본값: cwd/data

## 디렉토리

```
src/
├── core/
│   ├── config.py      # pydantic-settings
│   ├── logger.py      # loguru
│   └── llm.py         # LM Studio 클라이언트
├── memory/
│   ├── long_term.py   # SQLite (aiosqlite)
│   ├── short_term.py  # 컨텍스트 윈도우
│   └── rag_store.py   # ChromaDB
├── agents/
│   ├── tools.py
│   ├── chat_agent.py
│   ├── rag_agent.py
│   └── supervisor.py  # LangGraph
├── telegram/
│   ├── bot.py
│   └── handlers.py
├── dashboard/
│   ├── server.py      # FastAPI + SSE
│   ├── events.py      # 이벤트 버스
│   └── static/index.html
└── main.py            # 진입점
```

## 트러블슈팅

| 증상 | 원인 / 대응 |
|------|-------------|
| `connection error` (healthcheck) | LM Studio 미실행 또는 포트 불일치 |
| `model '...' not loaded` | LM Studio에서 모델을 로드하지 않음 |
| 봇이 응답 없음 | `TELEGRAM_BOT_TOKEN` 오타, 또는 `TELEGRAM_CHAT_ID`에 본인 ID 미포함 |
| RAG 검색 결과 0개 | `/ingest`로 문서 추가 또는 `RAG_SCORE_THRESHOLD` 낮추기 |
| 대시보드 502 | `DASHBOARD_PORT` 충돌 — 다른 포트로 변경 |
