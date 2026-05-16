# Mureka Studio API

FastAPI 백엔드 + Celery 워커. `docs/03-Architecture.md`에 정의된 명세를 구현합니다.

## 로컬 실행

### 1. 의존성 설치 (uv 권장)

```bash
cd apps/api
pip install -e ".[dev]"
# 또는
uv pip install -e ".[dev]"
```

### 2. 환경 변수

```bash
cp .env.example .env
# MUREKA_API_KEY, OPENAI_API_KEY 등 입력
```

`MUREKA_API_KEY`는 **백엔드 전용** 입니다. 절대 프론트엔드 환경 변수
(`NEXT_PUBLIC_*`)에 넣지 마세요.

### 3. 인프라 실행

레포 루트에서:

```bash
make dev   # docker-compose up (postgres + redis + minio + api + worker + beat)
```

### 4. 마이그레이션

API 컨테이너 진입 후 또는 로컬에서:

```bash
make migrate   # alembic upgrade head
```

### 5. 테스트

```bash
make test
# 또는
cd apps/api && pytest
```

기본적으로 `aiosqlite` 인메모리 DB를 사용합니다. 실제 Postgres에 대해
실행하려면:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/test_db pytest
```

### 6. 린트 / 포맷

```bash
make lint
make format
```

## 구조

```
app/
  main.py              # FastAPI factory
  config.py            # pydantic-settings
  db.py                # async engine + session
  deps.py              # JWT auth, session DI
  core/
    logging.py         # structlog + JSON
    exceptions.py      # RFC 7807 (Problem+JSON)
    middleware.py      # trace-id 전파
    tracing.py
  routers/
    songs.py           # POST/GET /api/v1/songs, SSE
    lyrics.py          # POST /api/v1/lyrics/generate
    library.py         # GET /api/v1/library (커서 페이징)
    account.py         # GET /api/v1/account/credits
    health.py
  services/
    mureka_client.py   # 비동기 Mureka REST 클라이언트 + retry
    sse_hub.py         # Redis pub/sub
    credits.py         # Saga (hold/charge/refund)
    moderation.py      # OpenAI Moderation + fallback
    storage.py         # S3/MinIO 추상화 (boto3)
    auth_service.py    # JWT 발급, bcrypt
  workers/
    celery_app.py      # Celery 앱 + 큐 라우팅
    poll_task.py       # Mureka 폴링 + 결과 저장 + 크레딧 정산
    cleanup_task.py    # 30일 만료 cron
    _sync_db.py        # sync SQLAlchemy 세션 (워커용)
  models/              # SQLAlchemy 2.0 (ERD 그대로)
  schemas/             # Pydantic v2
  migrations/
    env.py
    versions/0001_initial.py
```

## Mureka 응답 스키마가 실제와 다를 때

`docs/03-Architecture.md` 부록 A에 따라 Mureka 공식 응답 형태는 추후 확정
예정입니다. 호환 레이어를 단일 파일에 격리했으므로 다음 위치만 수정하면
나머지 코드는 그대로 동작합니다:

1. **`app/services/mureka_client.py` 의 `_parse_items()`**
   - `items` 키, 필드명(`url`, `audio_url`, `duration_ms` 등) 변경 시
2. **`_STATE_MAP`**
   - 상태 명칭(`pending`/`succeeded`/`completed`/...) 추가/매핑
3. **`MurekaTaskStatus` / `MurekaTaskItem` Pydantic 모델**
   - 새로운 필드를 노출하고 싶을 때

워커 (`poll_task.py`)는 추상화된 모델만 사용하므로 영향이 없습니다.

## 핵심 설계 결정 (DECISIONS)

- **비동기**: Mureka는 `task_id` 폴링이라 동기 응답 불가 -> Celery + 5초 폴
- **SSE**: 진행률은 Redis pubsub -> SSE 단방향 푸시 (WS 대비 운영 단순)
- **크레딧 Saga**: 요청 시점 `hold(-1)`, 완료 시 `charge(0)` 마커, 실패
  시 `refund(+1)` -> `credit_ledger`의 SUM이 진실
- **MUREKA_API_KEY**: pydantic `SecretStr` + 응답 페이로드 어디에도 비포함
- **Mureka 응답 추상화**: `MurekaTaskStatus` Pydantic 모델 + tolerant 파서

## API 명세 매핑

| Spec | Endpoint | Handler |
|---|---|---|
| 4.2 | `POST /api/v1/songs` | `routers.songs.create_generation` |
| 4.3 | `GET /api/v1/songs/{id}` | `routers.songs.get_generation` |
| 4.4 | `GET /api/v1/songs/{id}/stream` | `routers.songs.stream_generation` |
| 4.5 | `POST /api/v1/lyrics/generate` | `routers.lyrics.generate_lyrics` |
| 4.6 | `GET /api/v1/library` | `routers.library.list_library` |
| 4.7 | `GET /api/v1/account/credits` | `routers.account.get_credits` |
