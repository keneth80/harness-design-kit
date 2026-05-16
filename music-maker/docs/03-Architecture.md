# 03-Architecture: Music Maker — 시스템 아키텍처 설계서

> 작성일: 2026-05-15
> 기반 문서: `docs/01-PRD.md`, `docs/02-UX-Design.md`
> 상태: Draft v0.1
> 코드네임: **mureka-studio**

---

## 0. 아키텍처 핵심 결정 (Summary)

| # | 결정 | 이유 |
|---|---|---|
| A1 | **비동기 작업 모델 (Celery + Redis)** | Mureka API가 `task_id` 기반 폴링 방식이라 동기 요청 시 P95 60초 응답 불가 |
| A2 | **모노레포 (Turbo + uv workspace)** | Next.js(웹) + FastAPI(API/Worker) + 공유 타입을 단일 PR로 변경 |
| A3 | **SSE (Server-Sent Events) 우선** | WebSocket보다 인프라 단순, 단방향 진행률 푸시에 충분 |
| A4 | **S3 호환 스토리지 (개발=MinIO, 운영=AWS S3)** | 30일 만료 정책을 라이프사이클로 위임, 로컬은 동일 인터페이스 유지 |
| A5 | **사전 크레딧 차감 + 환불 패턴** | 비동기 환경에서도 잔액 일관성 보장 (Saga 패턴) |
| A6 | **공유 타입은 `shared-types` 패키지 (Python ↔ TS)** | Pydantic 스키마 → TS 타입 자동 생성 (`datamodel-code-generator`) |

---

## 1. 전체 시스템 다이어그램

### 1.1 컴포넌트 다이어그램

```mermaid
graph TB
    subgraph Client
        U[User Browser]
        WEB[Next.js 15 App Router<br/>SSR + RSC + Server Actions]
    end

    subgraph Edge["Edge / BFF"]
        BFF[Next.js Route Handlers<br/>/api - Auth Proxy Only]
    end

    subgraph Backend["FastAPI Backend"]
        GW[API Gateway<br/>FastAPI + Uvicorn]
        AUTH[Auth Service<br/>JWT + OAuth]
        SONG[Songs Router]
        LYR[Lyrics Router]
        LIB[Library Router]
        BIL[Billing Router]
        SSE[SSE Hub]
    end

    subgraph Workers["Celery Workers"]
        W1[Generation Worker<br/>poll_task.py]
        W2[Stem Separator Worker]
        W3[Cleanup Worker<br/>cron 30d expire]
    end

    subgraph Data["Data Layer"]
        PG[(PostgreSQL 16<br/>metadata)]
        RDS[(Redis 7<br/>queue + cache + SSE pub/sub)]
        S3[(S3 / MinIO<br/>audio files)]
    end

    subgraph External
        MUR[Mureka API<br/>song / lyrics / stems / tts]
        MOD[OpenAI Moderation]
        OAUTH[Google OAuth]
        STRIPE[Stripe Billing]
        SEN[Sentry]
    end

    U --> WEB
    WEB --> BFF
    BFF -->|HTTPS + JWT| GW
    GW --> AUTH
    GW --> SONG
    GW --> LYR
    GW --> LIB
    GW --> BIL

    SONG --> RDS
    LYR --> RDS
    SONG --> PG
    LIB --> PG
    BIL --> PG

    RDS -.task queue.-> W1
    RDS -.task queue.-> W2
    W1 -->|poll task_id| MUR
    W1 --> MOD
    W1 -->|store mp3/wav| S3
    W1 --> PG
    W1 -.publish.-> RDS
    RDS -.subscribe.-> SSE
    SSE -->|EventStream| WEB

    AUTH --> OAUTH
    BIL --> STRIPE
    GW --> SEN
    W1 --> SEN
    W3 --> S3
    W3 --> PG
```

### 1.2 요청 흐름 (생성 요청 1건)

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant WEB as Next.js
    participant API as FastAPI
    participant PG as Postgres
    participant Q as Redis Queue
    participant W as Celery Worker
    participant M as Mureka
    participant S3 as S3
    participant SSE as SSE Hub

    U->>WEB: 생성 폼 제출
    WEB->>API: POST /api/v1/songs (JWT)
    API->>PG: BEGIN: 크레딧 -1 (Hold)
    API->>PG: INSERT generations(status=queued)
    API->>Q: enqueue(generation_id)
    API-->>WEB: 202 Accepted {generation_id}
    WEB-->>U: Studio 진행 화면 + SSE 연결
    WEB->>SSE: GET /api/v1/events/{generation_id}
    Q->>W: dispatch
    W->>M: POST /song/generate
    M-->>W: {task_id, status: pending}
    W->>PG: UPDATE status=processing, task_id
    W->>SSE: publish progress=10%
    SSE-->>WEB: event: progress {10}
    loop 5초 간격 폴링 (최대 60회)
        W->>M: GET /task/{task_id}
        M-->>W: status: processing | completed | failed
        W->>SSE: publish progress=N
    end
    M-->>W: status=completed + 2 songs URL
    W->>M: download mp3 (x2)
    W->>S3: upload mp3/wav + cover
    W->>PG: INSERT songs (x2), UPDATE generation status=completed
    W->>PG: COMMIT: 크레딧 차감 확정
    W->>SSE: publish completed {songs}
    SSE-->>WEB: event: completed
    WEB-->>U: A/B 결과 화면
```

---

## 2. 디렉토리 구조

```
mureka-studio/
├── apps/
│   ├── web/                              # Next.js 15
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   │   ├── sign-in/page.tsx
│   │   │   │   ├── sign-up/page.tsx
│   │   │   │   └── callback/route.ts     # OAuth callback
│   │   │   ├── (app)/
│   │   │   │   ├── dashboard/page.tsx
│   │   │   │   ├── studio/
│   │   │   │   │   ├── page.tsx          # 3-pane Studio
│   │   │   │   │   ├── lyrics/page.tsx   # 가사 에디터
│   │   │   │   │   └── result/[id]/page.tsx  # A/B 비교
│   │   │   │   ├── library/
│   │   │   │   │   ├── page.tsx
│   │   │   │   │   └── [trackId]/page.tsx
│   │   │   │   ├── projects/
│   │   │   │   │   ├── page.tsx
│   │   │   │   │   └── [projectId]/page.tsx
│   │   │   │   ├── settings/page.tsx
│   │   │   │   └── billing/page.tsx
│   │   │   ├── layout.tsx
│   │   │   ├── globals.css
│   │   │   └── api/                      # BFF
│   │   │       ├── auth/[...nextauth]/route.ts
│   │   │       └── events/[generationId]/route.ts  # SSE proxy
│   │   ├── components/
│   │   │   ├── ui/                       # shadcn/ui generated
│   │   │   │   ├── button.tsx
│   │   │   │   ├── dialog.tsx
│   │   │   │   └── ...
│   │   │   ├── studio/
│   │   │   │   ├── prompt-input.tsx
│   │   │   │   ├── lyrics-editor.tsx
│   │   │   │   ├── style-picker.tsx
│   │   │   │   ├── generation-progress.tsx
│   │   │   │   ├── ab-compare.tsx
│   │   │   │   └── waveform-player.tsx   # wavesurfer.js wrapper
│   │   │   ├── library/
│   │   │   │   ├── library-grid.tsx
│   │   │   │   └── track-card.tsx
│   │   │   └── shared/
│   │   │       ├── credit-meter.tsx
│   │   │       └── nav-bar.tsx
│   │   ├── lib/
│   │   │   ├── api-client.ts             # typed fetch wrapper
│   │   │   ├── sse-client.ts             # EventSource hook
│   │   │   ├── auth.ts
│   │   │   └── format.ts
│   │   ├── hooks/
│   │   │   ├── use-generation.ts
│   │   │   ├── use-library.ts
│   │   │   └── use-credits.ts
│   │   ├── public/
│   │   ├── tailwind.config.ts
│   │   ├── next.config.mjs
│   │   └── package.json
│   │
│   └── api/                              # FastAPI
│       ├── app/
│       │   ├── main.py                   # FastAPI app factory
│       │   ├── config.py                 # pydantic-settings
│       │   ├── deps.py                   # DI: db, current_user
│       │   ├── routers/
│       │   │   ├── __init__.py
│       │   │   ├── songs.py
│       │   │   ├── lyrics.py
│       │   │   ├── library.py
│       │   │   ├── billing.py
│       │   │   ├── account.py
│       │   │   └── events.py             # SSE endpoint
│       │   ├── services/
│       │   │   ├── mureka_client.py      # Mureka REST 래퍼
│       │   │   ├── moderation.py         # OpenAI Moderation
│       │   │   ├── storage.py            # S3/MinIO 추상화
│       │   │   ├── credits.py            # 차감/환불 로직
│       │   │   ├── sse_hub.py            # Redis pub/sub
│       │   │   └── auth_service.py
│       │   ├── workers/
│       │   │   ├── celery_app.py
│       │   │   ├── poll_task.py          # Mureka 폴링 워커
│       │   │   ├── stem_task.py          # 스템 분리
│       │   │   └── cleanup_task.py       # 30일 만료 cron
│       │   ├── models/                   # SQLAlchemy 2.0
│       │   │   ├── __init__.py
│       │   │   ├── base.py
│       │   │   ├── user.py
│       │   │   ├── generation.py
│       │   │   ├── song.py
│       │   │   ├── preset.py
│       │   │   ├── project.py
│       │   │   └── credit_ledger.py
│       │   ├── schemas/                  # Pydantic v2
│       │   │   ├── song.py
│       │   │   ├── lyrics.py
│       │   │   ├── library.py
│       │   │   ├── billing.py
│       │   │   └── events.py
│       │   ├── core/
│       │   │   ├── logging.py
│       │   │   ├── tracing.py            # trace_id, mureka_trace_id
│       │   │   ├── rate_limit.py
│       │   │   └── exceptions.py
│       │   └── migrations/               # Alembic
│       │       └── versions/
│       ├── tests/
│       │   ├── conftest.py
│       │   ├── unit/
│       │   └── integration/
│       ├── alembic.ini
│       ├── pyproject.toml
│       └── Dockerfile
│
├── packages/
│   └── shared-types/
│       ├── src/
│       │   ├── python/                   # source of truth (Pydantic)
│       │   └── typescript/               # auto-generated TS
│       ├── scripts/
│       │   └── generate-ts.sh            # pydantic -> TS
│       └── package.json
│
├── infra/
│   ├── docker/
│   │   ├── postgres.Dockerfile
│   │   └── minio.Dockerfile
│   └── k8s/                              # v1.0+
│
├── docker-compose.yml                    # local dev: web + api + worker + pg + redis + minio
├── docker-compose.prod.yml
├── turbo.json
├── pnpm-workspace.yaml
├── .env.example
├── README.md
└── docs/
    ├── 01-PRD.md
    ├── 02-UX-Design.md
    └── 03-Architecture.md
```

### 2.1 패키지 매니저 / 빌드 도구

| 영역 | 도구 |
|---|---|
| 모노레포 | Turbo + pnpm workspace |
| Node | pnpm 9.x |
| Python | uv (정적 lock) + ruff + mypy |
| 컨테이너 | Docker Compose (local), Helm (prod) |
| 마이그레이션 | Alembic |

---

## 3. 데이터 모델 (PostgreSQL ERD)

### 3.1 ERD

```mermaid
erDiagram
    USERS ||--o{ GENERATIONS : creates
    USERS ||--o{ PRESETS : owns
    USERS ||--o{ PROJECTS : owns
    USERS ||--o{ CREDIT_LEDGER : holds
    GENERATIONS ||--o{ SONGS : produces
    GENERATIONS }o--|| PRESETS : "used (nullable)"
    PROJECTS ||--o{ SONGS : contains
    SONGS ||--o{ STEMS : "separated (nullable)"

    USERS {
        uuid id PK
        text email UK
        text name
        text avatar_url
        int credits "denormalized cache"
        text plan "free|pro|studio"
        text auth_provider
        text auth_provider_id
        timestamptz created_at
        timestamptz updated_at
    }

    GENERATIONS {
        uuid id PK
        uuid user_id FK
        uuid project_id FK "nullable"
        uuid preset_id FK "nullable"
        text task_id "Mureka task_id"
        text status "queued|processing|completed|failed|cancelled"
        text mode "song|instrumental|tts"
        jsonb prompt "{text, length_s, genres, moods, bpm, key}"
        text lyrics "nullable, raw with structure tags"
        text model "mureka-7|mureka-o1"
        int progress "0-100"
        text mureka_trace_id "for debugging"
        text error_code "nullable"
        text error_message "nullable"
        int credit_cost
        timestamptz created_at
        timestamptz completed_at
        timestamptz expires_at
    }

    SONGS {
        uuid id PK
        uuid generation_id FK
        uuid project_id FK "nullable"
        text mureka_song_id UK
        text variant "A|B"
        text storage_key "s3://bucket/key"
        text mp3_url "presigned, cached"
        text wav_url "presigned, cached"
        text cover_url
        int duration_ms
        int bpm
        text key
        text[] genres
        text[] moods
        boolean is_favorite
        text[] tags
        timestamptz created_at
        timestamptz expires_at
    }

    STEMS {
        uuid id PK
        uuid song_id FK
        text stem_type "vocals|drums|bass|melody|other"
        text storage_key
        int duration_ms
        timestamptz created_at
    }

    PRESETS {
        uuid id PK
        uuid user_id FK
        text name
        jsonb style_prompt "genres, moods, bpm, instruments"
        text model
        boolean is_default
        timestamptz created_at
    }

    PROJECTS {
        uuid id PK
        uuid user_id FK
        text name
        text description
        text cover_url
        text share_token "nullable, unique"
        timestamptz created_at
    }

    CREDIT_LEDGER {
        uuid id PK
        uuid user_id FK
        uuid generation_id FK "nullable"
        text type "hold|charge|refund|grant|purchase"
        int amount "signed: + grant, - charge"
        text reason
        text stripe_payment_intent "nullable"
        timestamptz created_at
    }
```

### 3.2 인덱스 전략

| 테이블 | 인덱스 | 이유 |
|---|---|---|
| `generations` | `(user_id, created_at DESC)` | 사용자 히스토리 페이징 |
| `generations` | `(status, created_at)` partial WHERE status IN ('queued','processing') | 워커 재시작 시 미완료 작업 회수 |
| `generations` | `(task_id)` UNIQUE | Mureka task_id 역조회 |
| `songs` | `(generation_id)` | 생성건 → 곡 조인 |
| `songs` | `(user_id, is_favorite, created_at DESC)` via materialized view | 라이브러리 필터 |
| `songs` | `genres` GIN | 태그 검색 |
| `credit_ledger` | `(user_id, created_at DESC)` | 잔액 계산 |

### 3.3 크레딧 잔액 계산 (Source of Truth)

- `users.credits` 는 **캐시**일 뿐, 진실은 `credit_ledger`의 SUM(amount)
- 트리거나 cron으로 5분마다 sync, 불일치 시 알람
- 차감/환불은 항상 `credit_ledger` INSERT (불변 로그)

---

## 4. API 명세 (자체 BE, OpenAPI 스타일)

### 4.1 공통

- Base URL: `https://api.music-maker.app/api/v1`
- 인증: `Authorization: Bearer <JWT>` (Access 15min, Refresh 14d)
- 컨텐츠 타입: `application/json; charset=utf-8`
- 에러 포맷: RFC 7807 Problem+JSON

```json
{
  "type": "https://docs.music-maker.app/errors/insufficient-credits",
  "title": "Insufficient credits",
  "status": 402,
  "detail": "Need 1 credit, have 0",
  "instance": "/api/v1/songs",
  "trace_id": "01HXG..."
}
```

### 4.2 POST /api/v1/songs — 음원 생성 요청

> 생성 요청. 즉시 `generation_id` 반환 (실제 작업은 워커가 비동기 처리).

**Request**:
```json
{
  "mode": "song",
  "prompt": {
    "text": "비 오는 도쿄 새벽, 잔잔한 피아노",
    "length_s": 90,
    "genres": ["lo-fi"],
    "moods": ["melancholy"],
    "bpm": 90,
    "key": "Cm"
  },
  "lyrics": "[Verse 1]\n도시는 잠들지 않아\n...",
  "lyrics_mode": "user|ai|none",
  "model": "mureka-7",
  "preset_id": null,
  "project_id": null
}
```

**Response 202 Accepted**:
```json
{
  "generation_id": "01HXG7E2K4Q...",
  "status": "queued",
  "estimated_seconds": 45,
  "credit_cost": 1,
  "credits_remaining": 41,
  "subscribe_url": "/api/v1/events/01HXG7E2K4Q..."
}
```

**Errors**:
| Status | Code | 의미 |
|---|---|---|
| 400 | `invalid_prompt` | 프롬프트 유효성 실패 |
| 402 | `insufficient_credits` | 잔액 부족 |
| 422 | `moderation_blocked` | 입력 모더레이션 실패 |
| 429 | `rate_limit_exceeded` | 시간당 20건 초과 |

### 4.3 GET /api/v1/songs/{generation_id} — 상태/결과 조회

**Response 200** (processing 중):
```json
{
  "generation_id": "01HXG...",
  "status": "processing",
  "progress": 42,
  "stage": "vocal_synthesis",
  "started_at": "2026-05-15T20:30:00Z",
  "estimated_remaining_s": 26
}
```

**Response 200** (completed):
```json
{
  "generation_id": "01HXG...",
  "status": "completed",
  "progress": 100,
  "credit_cost": 1,
  "songs": [
    {
      "id": "01HXG8...",
      "variant": "A",
      "mp3_url": "https://cdn.music-maker.app/s/A.mp3?sig=...",
      "wav_url": "https://cdn.music-maker.app/s/A.wav?sig=...",
      "duration_ms": 90000,
      "bpm": 90,
      "key": "Cm",
      "genres": ["lo-fi"],
      "moods": ["melancholy"],
      "cover_url": "https://cdn.music-maker.app/c/A.jpg"
    },
    { "id": "01HXG9...", "variant": "B", "...": "..." }
  ],
  "lyrics": "[Verse 1]\n...",
  "license_pdf_url": "https://cdn.music-maker.app/license/01HXG.pdf"
}
```

### 4.4 GET /api/v1/events/{generation_id} — SSE 스트림

**Response (text/event-stream)**:
```
: connected
data: {"event":"progress","progress":10,"stage":"lyrics_parsed"}

data: {"event":"progress","progress":42,"stage":"vocal_synthesis"}

data: {"event":"completed","songs":[...]}
```

자세한 이벤트 정의: 섹션 5.2 참조.

### 4.5 POST /api/v1/lyrics/generate — AI 가사 생성

**Request**:
```json
{
  "topic": "도시의 새벽, 그리움",
  "language": "ko",
  "tone": "emotional",
  "structure": ["verse", "chorus", "verse", "chorus", "bridge", "chorus"],
  "syllables_per_line": 8
}
```

**Response 200** (동기, 5초 내 완료):
```json
{
  "lyrics": "[Verse 1]\n도시는 잠들지 않아\n...",
  "moderation": { "flagged": false },
  "credit_cost": 0
}
```

> 가사 생성은 짧고 가벼워 동기 응답. 모더레이션 실패 시 422.

### 4.6 GET /api/v1/library — 라이브러리 (커서 페이징)

**Query**:
```
?cursor=eyJjIjoyMDI2...&limit=24
&filter[genres]=lo-fi,jazz
&filter[favorites]=true
&filter[project_id]=01HX...
&sort=-created_at
```

**Response 200**:
```json
{
  "items": [
    {
      "id": "01HXG8...",
      "generation_id": "01HXG...",
      "variant": "A",
      "title": "Tokyo Rain - A",
      "duration_ms": 90000,
      "cover_url": "...",
      "mp3_url": "...",
      "is_favorite": true,
      "tags": ["lofi", "rain"],
      "created_at": "2026-05-15T20:42:00Z"
    }
  ],
  "next_cursor": "eyJjIjoyMDI2..." 
}
```

### 4.7 GET /api/v1/account/credits — 크레딧 잔액 & 사용량

**Response 200**:
```json
{
  "credits": 41,
  "plan": "pro",
  "plan_quota_per_month": 100,
  "used_this_month": 59,
  "renews_at": "2026-06-01T00:00:00Z",
  "ledger_preview": [
    { "type": "charge", "amount": -1, "reason": "song_generation", "at": "2026-05-15T20:30:00Z" },
    { "type": "grant", "amount": 100, "reason": "monthly_renewal", "at": "2026-05-01T00:00:00Z" }
  ]
}
```

### 4.8 기타 엔드포인트 요약

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/songs/{id}/stems` | 스템 분리 요청 (비동기) |
| POST | `/api/v1/songs/{id}/favorite` | 즐겨찾기 토글 |
| GET | `/api/v1/songs/{id}/download?format=mp3\|wav` | 서명 URL 반환 |
| GET | `/api/v1/presets` / POST | 프리셋 CRUD |
| POST | `/api/v1/projects` / GET | 프로젝트 CRUD |
| POST | `/api/v1/projects/{id}/share` | 공유 링크 발급 |
| POST | `/api/v1/billing/checkout` | Stripe Checkout 세션 |
| POST | `/api/v1/billing/webhook` | Stripe Webhook (HMAC 검증) |

---

## 5. 비동기 처리 전략

### 5.1 Celery 워커 토폴로지

| 큐 | 워커 | 동시성 | 우선순위 | 타임아웃 |
|---|---|---|---|---|
| `generation:high` | `poll_task` (유료) | 8 | 9 | 300s |
| `generation:normal` | `poll_task` (무료) | 4 | 5 | 300s |
| `stem:default` | `stem_task` | 2 | 5 | 600s |
| `cleanup:cron` | `cleanup_task` | 1 | 1 | 1800s |

> 동시 10건 (NFR) 충족을 위해 high+normal=12 worker로 여유 확보.

### 5.2 Mureka 폴링 워커 (`poll_task.py`) 의사 코드

```python
# apps/api/app/workers/poll_task.py
from celery import shared_task
from app.services.mureka_client import MurekaClient
from app.services.sse_hub import publish

POLL_INTERVAL_S = 5
MAX_POLL_COUNT = 60   # 5분 타임아웃
MAX_RETRIES = 2

@shared_task(bind=True, max_retries=MAX_RETRIES, autoretry_for=(MurekaTransientError,))
def run_generation(self, generation_id: str) -> None:
    gen = db.get_generation(generation_id)
    try:
        with credits.hold(gen.user_id, gen.credit_cost):
            task = mureka.create_song(gen.prompt, gen.lyrics, gen.model)
            db.update(gen.id, task_id=task.id, mureka_trace_id=task.trace_id, status="processing")
            publish(gen.id, {"event": "progress", "progress": 10, "stage": "submitted"})

            for i in range(MAX_POLL_COUNT):
                time.sleep(POLL_INTERVAL_S)
                status = mureka.get_task(task.id)
                progress = min(10 + i * 1.5, 95)
                publish(gen.id, {"event": "progress", "progress": progress, "stage": status.stage})

                if status.state == "completed":
                    songs = []
                    for variant, item in zip(["A", "B"], status.items):
                        mp3 = mureka.download(item.url)
                        key = storage.put(f"songs/{gen.id}/{variant}.mp3", mp3)
                        songs.append(db.insert_song(gen.id, variant, key, item.meta))
                    db.update(gen.id, status="completed", progress=100)
                    credits.commit(gen.user_id, gen.credit_cost, generation_id=gen.id)
                    publish(gen.id, {"event": "completed", "songs": [s.public() for s in songs]})
                    return

                if status.state == "failed":
                    raise MurekaTaskFailed(status.error_code, status.error_message)

            raise MurekaTimeoutError("polling exceeded 5 minutes")

    except (MurekaTimeoutError, MurekaTaskFailed) as e:
        if self.request.retries < MAX_RETRIES:
            publish(generation_id, {"event": "retrying", "attempt": self.request.retries + 1})
            raise self.retry(exc=e, countdown=2 ** self.request.retries * 2)
        credits.refund(gen.user_id, gen.credit_cost, reason=str(e))
        db.update(gen.id, status="failed", error_code=e.code, error_message=str(e))
        publish(gen.id, {"event": "failed", "error": e.code, "refunded": gen.credit_cost})
```

### 5.3 SSE 이벤트 스키마

```typescript
type GenerationEvent =
  | { event: "queued"; position: number }
  | { event: "progress"; progress: number; stage: string; estimated_remaining_s?: number }
  | { event: "retrying"; attempt: number }
  | { event: "completed"; songs: SongPublic[] }
  | { event: "failed"; error: string; refunded: number }
  | { event: "ping" };  // keep-alive 매 25초
```

### 5.4 SSE Hub 구현 (Redis Pub/Sub)

```
Worker  ─ PUBLISH gen:{generation_id} {json}
                                              \
                                               ↓
SSE endpoint (FastAPI StreamingResponse)
   ─ SUBSCRIBE gen:{generation_id}
   ─ async for msg in pubsub: yield f"data: {msg}\n\n"
```

- 연결 끊김 대비 `Last-Event-ID` 헤더로 마지막 progress 재전송
- 25초마다 `ping` 이벤트로 keep-alive (프록시 timeout 회피)

### 5.5 재시도 & 타임아웃 정책

| 상황 | 동작 |
|---|---|
| Mureka 5xx | exponential backoff (4s → 8s), 최대 2회 |
| Mureka task `failed` | 즉시 1회 재시도, 그래도 실패 시 환불 |
| 폴링 60회(5분) 초과 | 타임아웃 처리 → 환불 |
| 워커 OOM/Crash | Celery `acks_late=True` + visibility timeout 320s, 자동 재할당 |
| 클라이언트 SSE 끊김 | 클라이언트가 자동 재연결 (EventSource 기본 동작) |

### 5.6 멱등성 (Idempotency)

- 클라이언트가 `Idempotency-Key` 헤더 동봉 시, 동일 키 24시간 내 재요청은 같은 `generation_id` 반환
- Redis SET NX EX 86400 으로 보장

---

## 6. 보안 & 비용

### 6.1 시크릿 관리

| 시크릿 | 저장 위치 | 접근 가능 |
|---|---|---|
| `MUREKA_API_KEY` | AWS Secrets Manager (prod), `.env` (local) | FastAPI/Worker only |
| `OPENAI_API_KEY` (모더레이션) | 동일 | FastAPI/Worker only |
| `STRIPE_SECRET_KEY` | 동일 | FastAPI only |
| `JWT_SIGNING_KEY` | 동일 | FastAPI only |
| `DATABASE_URL` | 동일 | FastAPI/Worker/Migrations |

**원칙**:
- [x] **Mureka API Key는 어떤 경우에도 클라이언트에 노출 금지** — Next.js에서 직접 호출 금지
- [x] `NEXT_PUBLIC_*` 환경변수에는 외부 API 키 절대 금지
- [x] Mureka 호출은 100% FastAPI 백엔드/워커 경유
- [x] 로그/Sentry에 시크릿이 들어가지 않도록 `SecretStr` + `logging.Filter`

### 6.2 인증/인가

- JWT (Access 15min) + Refresh (HttpOnly Secure cookie, 14d)
- OAuth: Google (Beta), Apple (v1.0)
- 모든 `/api/v1/*` 엔드포인트는 `Depends(get_current_user)`
- 본인 리소스 접근만 허용 (`generation.user_id == current_user.id`)
- 공유 링크는 별도 `share_token` 기반 비로그인 접근 (read-only)

### 6.3 Rate Limiting

| 범위 | 한도 | 구현 |
|---|---|---|
| 사용자당 생성 요청 | **시간당 20건** | Redis sliding window |
| 사용자당 가사 생성 | 시간당 60건 | 동일 |
| 무료 플랜 | 일 5건 | 별도 카운터 |
| IP당 익명 요청 | 분당 30건 | Cloudflare Turnstile + edge rate limit |
| Mureka API 자체 호출 | 동시 12건 (워커 수) | Celery 동시성으로 자연 제한 |

### 6.4 크레딧 시스템 (Saga 패턴)

```
1) API: ledger INSERT type=hold, amount=-1  (Pending)
2) Worker: 작업 시작 (성공 시) → ledger INSERT type=charge, amount=-1 + 기존 hold 정산
3) Worker: 실패 시 → ledger INSERT type=refund, amount=+1 + hold 취소
```

- 잔액은 항상 `SUM(amount) FROM credit_ledger WHERE user_id=?`
- `users.credits` 캐시는 트랜잭션 commit 후 update
- 결제 후 grant: Stripe webhook → `ledger INSERT type=grant`

### 6.5 음원 파일 라이프사이클

| 파일 | 보관 기간 | 정책 |
|---|---|---|
| 생성된 mp3/wav | **30일** (무료) / 무제한 (유료) | S3 Lifecycle Policy + 우리 cron `cleanup_task` 이중 보장 |
| 즐겨찾기/프로젝트 추가된 곡 | 무제한 | `expires_at = NULL` |
| 스템 파일 | 30일 (모든 플랜) | 용량 큼 |
| 임시 업로드 (보컬 클로닝) | 24시간 | 처리 후 즉시 삭제 |

**cleanup_task.py**:
```python
@celery.task
def cleanup_expired_files():
    expired = db.query(Song).filter(
        Song.expires_at < now(), Song.is_favorite == False,
        Song.project_id.is_(None)
    ).limit(1000).all()
    for song in expired:
        storage.delete(song.storage_key)
        db.delete(song)
    logger.info("cleaned %d files", len(expired))
```

### 6.6 콘텐츠 보안

- 가사 입력/출력 2단계 모더레이션 (PRD R3 대응)
- 보컬 클로닝: 신원 확인 챌린지 + 비가청 워터마크
- 모든 생성물에 EXIF/메타데이터로 `produced_by=music-maker, gen_id=...` 삽입

---

## 7. 관측성 (Observability)

### 7.1 로깅

| 항목 | 사양 |
|---|---|
| 포맷 | JSON 구조화 로그 (`structlog` + `python-json-logger`) |
| 필수 필드 | `timestamp`, `level`, `trace_id`, `span_id`, `user_id`, `generation_id`, `mureka_trace_id`, `event`, `msg` |
| 보관 | CloudWatch Logs 30일, Critical은 90일 |
| 민감 필드 | `email`, `api_key`, `lyrics` 본문은 자동 마스킹 |

**Mureka trace_id 기록**:
```python
# 모든 Mureka API 응답 헤더 X-Trace-Id를 추출하여 generation에 저장
log.info("mureka.task.created",
         generation_id=gen.id,
         mureka_task_id=task.id,
         mureka_trace_id=task.headers["x-trace-id"])
```

### 7.2 메트릭 (Prometheus)

| 메트릭 | 타입 | 라벨 |
|---|---|---|
| `generation_requests_total` | counter | `mode`, `model`, `plan` |
| `generation_success_total` | counter | `model` |
| `generation_failures_total` | counter | `error_code` |
| `generation_duration_seconds` | histogram | `model`, buckets=[10,30,45,60,90,180,300] |
| `mureka_poll_count` | histogram | `result` |
| `mureka_api_latency_seconds` | histogram | `endpoint` |
| `credits_balance` | gauge | `plan` (sum per plan) |
| `sse_active_connections` | gauge | — |
| `worker_queue_depth` | gauge | `queue` |

**대시보드 (Grafana)**:
- 생성 성공률: `success / (success + failures)` (목표 ≥ 95%)
- 평균 폴링 횟수: `histogram_quantile(0.5, mureka_poll_count)`
- 평균 소요 시간: `histogram_quantile(0.5, generation_duration_seconds)`

### 7.3 에러 트래킹 (Sentry)

**연동 지점**:
- [x] FastAPI: `SentryAsgiMiddleware`, 모든 5xx 자동 캡처
- [x] Celery: `sentry_sdk.integrations.celery.CeleryIntegration`
- [x] Next.js: `@sentry/nextjs`, RSC + Client Component 모두 커버
- [x] 사용자 컨텍스트: `sentry_sdk.set_user({id, email_hash})`
- [x] 태그: `mureka_trace_id`, `generation_id` (검색 가능)

**Sentry 무시 규칙**:
- 클라이언트 ResizeObserver 경고, AbortError 등 무관 노이즈는 `beforeSend` 필터링
- Mureka 4xx (입력 오류)는 Sentry로 보내지 않음 (모니터링은 메트릭으로)

### 7.4 분산 추적 (OpenTelemetry)

- 트레이스 컨텍스트 전파: 클라이언트 `traceparent` → Next.js → FastAPI → Celery → Mureka
- Mureka 호출은 SPAN 으로 wrap, `mureka_trace_id`를 SPAN attribute로 첨부
- 백엔드 Exporter: Tempo (Grafana Cloud) 또는 Jaeger (self-hosted)

### 7.5 알림 규칙

| 조건 | 채널 | 우선순위 |
|---|---|---|
| 생성 성공률 < 90% (5분 평균) | PagerDuty | P1 |
| Mureka API 5xx > 5/min | Slack #alerts | P2 |
| Celery 큐 깊이 > 100 (5분) | Slack | P2 |
| 일 API 비용 > 예상치 200% | Slack + 이메일 | P1 |
| SSE 연결 실패율 > 5% | Slack | P3 |

---

## 8. 환경 변수 (.env.example 발췌)

```bash
# === App ===
APP_ENV=development
LOG_LEVEL=INFO

# === Database ===
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/mureka_studio
ALEMBIC_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/mureka_studio

# === Redis ===
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# === Storage ===
STORAGE_PROVIDER=minio   # minio | s3
STORAGE_ENDPOINT=http://localhost:9000
STORAGE_BUCKET=mureka-studio-dev
STORAGE_ACCESS_KEY=minioadmin
STORAGE_SECRET_KEY=minioadmin
CDN_BASE_URL=http://localhost:9000/mureka-studio-dev

# === Mureka (BACKEND ONLY - NEVER expose to client) ===
MUREKA_API_BASE=https://api.mureka.ai/v1
MUREKA_API_KEY=mk_xxxxxxxxxxxxxxxxxxxxxx
MUREKA_TIMEOUT_S=30

# === Moderation ===
OPENAI_API_KEY=sk-xxx
MODERATION_ENABLED=true

# === Auth ===
JWT_SIGNING_KEY=<256-bit-random>
GOOGLE_OAUTH_CLIENT_ID=xxx
GOOGLE_OAUTH_CLIENT_SECRET=xxx

# === Billing ===
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# === Observability ===
SENTRY_DSN_API=https://xxx@sentry.io/xxx
SENTRY_DSN_WEB=https://xxx@sentry.io/xxx
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# === Next.js (apps/web/.env.local) ===
NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1
NEXT_PUBLIC_SENTRY_DSN=https://xxx@sentry.io/xxx
# NEXT_PUBLIC_MUREKA_API_KEY=  ← 절대 금지
```

---

## 9. 배포 토폴로지

### 9.1 Local (docker-compose)

```yaml
services:
  web:        # Next.js dev server, port 3000
  api:        # FastAPI uvicorn, port 8000
  worker:     # Celery worker x 2 replicas
  beat:       # Celery beat (cron)
  postgres:   # PG 16
  redis:      # Redis 7
  minio:      # S3 compatible
  mailhog:    # 로컬 이메일 캡처
```

### 9.2 Production (참고)

- **Web**: Vercel (Edge runtime + ISR)
- **API/Worker**: ECS Fargate (또는 Fly.io) — Worker 4 task 시작, Auto-scaling
- **DB**: RDS Postgres 16 Multi-AZ
- **Cache/Queue**: ElastiCache Redis (replication)
- **Object Storage**: S3 + CloudFront (서명 URL 5분 TTL)
- **CDN**: CloudFront
- **Secrets**: AWS Secrets Manager
- **Observability**: Grafana Cloud (Logs/Metrics/Tempo) + Sentry SaaS

---

## 10. 다음 단계 체크리스트

- [ ] `docker-compose.yml` 작성 (web/api/worker/pg/redis/minio)
- [ ] Alembic 초기 마이그레이션 (`users`, `generations`, `songs`, `credit_ledger`)
- [ ] `mureka_client.py` skeleton + Mureka 실제 응답 스키마 확인
- [ ] SSE endpoint 프로토타입 (heartbeat 포함)
- [ ] `shared-types` 자동 생성 스크립트 (Pydantic → TS)
- [ ] `/grill`로 API 명세 모호점 점검
- [ ] ADR-001 ~ ADR-004 작성: 비동기 모델 / SSE vs WebSocket / 모노레포 / 크레딧 Saga
- [ ] 부하 테스트 (k6): 동시 10건 생성 P95 ≤ 60초 검증

---

## 부록 A. Mureka API 통합 노트

| 항목 | 값/주의 |
|---|---|
| Base URL | `https://api.mureka.ai/v1` (실제 문서 재확인 필수) |
| 인증 | `Authorization: Bearer <API_KEY>` |
| 핵심 엔드포인트 | `POST /song/generate`, `POST /lyrics/generate`, `GET /task/{id}`, `POST /stems/separate`, `POST /tts` |
| 응답 형태 | `{task_id, status, trace_id}` → 폴링 필요 |
| 비용 | 곡 길이 + 모델별 차등 (정책 확인 후 `credit_cost` 매핑) |
| 동시 호출 한도 | (문서 재확인) — 우리 Celery 동시성과 매칭 |
| 결과 만료 | Mureka가 일정 기간 후 URL 만료 → 우리가 즉시 다운로드 후 자체 S3 저장 필수 |

## 부록 B. 용어 매핑 (CONTEXT.md 연동)

| 본 문서 용어 | 의미 |
|---|---|
| generation | 1회의 생성 요청 (1 credit, 2 songs 반환) |
| song | 생성 결과 1곡 (variant A 또는 B) |
| stem | song을 분리한 트랙 (vocals/drums/bass/melody) |
| preset | 사용자 저장한 스타일 설정 |
| ledger entry | credit_ledger 한 행 (hold/charge/refund/grant/purchase) |
