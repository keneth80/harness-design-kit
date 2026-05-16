# Backend Implementation Report — 2026-05-15

## 구현 범위 (apps/api/)

`docs/03-Architecture.md` 섹션 0~10 + 부록 A 를 기준으로 FastAPI 백엔드 +
Celery 워커를 1차 스캐폴딩 완료.

## 추가/수정한 파일 (트리)

```
apps/api/
├── pyproject.toml
├── alembic.ini
├── Dockerfile
├── .env.example
├── README.md
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── deps.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── logging.py
│   │   ├── tracing.py
│   │   ├── middleware.py
│   │   └── exceptions.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── songs.py
│   │   ├── lyrics.py
│   │   ├── library.py
│   │   ├── account.py
│   │   └── health.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── mureka_client.py
│   │   ├── sse_hub.py
│   │   ├── credits.py
│   │   ├── moderation.py
│   │   ├── storage.py
│   │   └── auth_service.py
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   ├── poll_task.py
│   │   ├── cleanup_task.py
│   │   └── _sync_db.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── generation.py
│   │   ├── song.py
│   │   ├── stem.py
│   │   ├── preset.py
│   │   ├── project.py
│   │   └── credit_ledger.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── song.py
│   │   ├── lyrics.py
│   │   ├── library.py
│   │   ├── billing.py
│   │   └── events.py
│   └── migrations/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
│           └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── unit/
    │   ├── __init__.py
    │   ├── test_mureka_client.py
    │   └── test_credits.py
    └── integration/
        ├── __init__.py
        ├── test_routers_songs.py
        └── test_worker_poll.py

# 루트
docker-compose.yml
Makefile
README.md
```

## 노출 엔드포인트 (docs/03-Architecture.md §4 매핑)

| Spec | Method/Path | Handler |
|---|---|---|
| 4.2 | `POST /api/v1/songs` | `routers.songs.create_generation` |
| 4.3 | `GET /api/v1/songs/{id}` | `routers.songs.get_generation` |
| 4.4 | `GET /api/v1/songs/{id}/stream` (SSE) | `routers.songs.stream_generation` |
| 4.5 | `POST /api/v1/lyrics/generate` | `routers.lyrics.generate_lyrics` |
| 4.6 | `GET /api/v1/library` | `routers.library.list_library` |
| 4.7 | `GET /api/v1/account/credits` | `routers.account.get_credits` |
| —   | `GET /healthz`, `GET /readyz` | `routers.health.*` |

## 핵심 제약 준수

- [x] Mureka 비동기 모델: API는 `202 Accepted`만 반환, 워커가 5초 폴링
- [x] `MUREKA_API_KEY` 는 `SecretStr` 으로 보호, 응답 어디에도 노출되지 않음
- [x] 크레딧 Saga: `hold(-amount)` → 완료 시 `charge(0)` 마커, 실패 시 `refund(+amount)`
- [x] RFC 7807 Problem+JSON 에러 + `X-Trace-Id` 헤더 전파
- [x] 본인 리소스 접근만 허용 (`generation.user_id == current_user.id`)

## 미해결 TODO / 가정 / 모호점

1. **Mureka 실제 응답 스키마**: 공식 문서 미공개. `mureka_client.py` 의
   `_parse_items()` + `_STATE_MAP` 이 호환 레이어. 실제 응답이 다르면
   해당 두 곳만 수정하면 됨 (`apps/api/README.md` 참조).
2. **WAV 다운로드**: PRD M4 는 MP3/WAV 둘 다 요구. 현재는 MP3만 저장. Mureka
   응답에 wav URL 이 별도로 오면 `poll_task._persist_songs` 에 추가.
3. **Stems 라우터**: 명세 4.8 (`POST /api/v1/songs/{id}/stems`) 는 스캐폴딩
   에서 제외 (Should-have). 모델은 있음.
4. **Billing / Stripe**: 스키마/모델은 있지만 라우터/Webhook 구현은 제외.
5. **OAuth (Google)**: `auth_service` 에 JWT 발급/검증만 있고 OAuth 콜백
   라우터는 미구현 (별도 PR).
6. **Idempotency-Key**: 명세 5.6 의 Redis SETNX 처리는 후속 작업으로 보류.
7. **Cursor pagination**: `library.py` 는 created_at 기반 단순 cursor.
   tie-breaker 까지는 보수적으로 가져갔지만 production 부하에서 검증 필요.

## 테스트 결과

```
14 passed in 0.25s
ruff: All checks passed!
```

- `tests/unit/test_mureka_client.py` — respx 모킹 6 케이스
  - generate_song happy path
  - query_task 상태 매핑 + items 파싱
  - 4xx 즉시 실패 (재시도 안 함)
  - 5xx 재시도 후 성공
  - 5xx 재시도 소진 → MurekaTransientError
  - generate_lyrics 텍스트 추출
- `tests/unit/test_credits.py` — Saga 2 케이스
  - hold 성공 + users.credits 캐시 갱신
  - 잔액 부족 시 InsufficientCreditsError
- `tests/integration/test_routers_songs.py` — 5 케이스
  - POST /songs → 202 + credit_ledger.hold 엔트리 생성
  - GET /songs/{id} → 다른 사용자 소유 시 403
  - GET /songs/{id} → 미존재 시 404
  - GET /account/credits → 잔액 응답
  - GET /library → 사용자 곡 목록 반환
- `tests/integration/test_worker_poll.py` — 워커 해피패스
  - Mureka 클라이언트/스토리지/SSE 모두 mock
  - 워커 실행 후 songs 2개 저장 + charge 마커 + completed SSE 이벤트 발행 검증

테스트는 기본적으로 `aiosqlite` 인메모리 + Postgres 전용 타입(JSONB, ARRAY,
UUID) 의 SQLite 호환 패치(`conftest._patch_postgres_types_for_sqlite`)로
무인프라 실행. 실제 Postgres 검증은 `TEST_DATABASE_URL` 환경변수로 가능.

## 적용한 lessons-learned 교훈

`docs/lessons-learned.md` 부재 — 해당 없음. 첫 오류 발생 시 error-curator
가 생성.

## 다음 액션

1. frontend-dev: `apps/api/README.md` 의 엔드포인트 매핑표로 typed fetch
   wrapper 구현
2. qa-engineer: boundary 검증 (모더레이션 차단, 크레딧 부족, 워커 타임아웃)
3. integration-dev (활성화 시): 실제 Mureka 응답 샘플 수집 → `_parse_items`
   조정
4. ADR 작성: 비동기 모델, SSE vs WebSocket, 크레딧 Saga, Mureka 응답 추상화
