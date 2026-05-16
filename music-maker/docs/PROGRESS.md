# Music Maker — 진행 상태

> **이 문서는 "어디까지 했고 다음 무엇을 해야 하는지"의 단일 진실원(Source of Truth)입니다.**
> 새 세션에서 작업을 이어가려면 이 파일을 가장 먼저 읽으세요.
> 의미 있는 작업이 끝날 때마다 "Last updated" 와 해당 섹션을 갱신하세요.

- **Last updated**: 2026-05-16 (ADR 4건 작성)
- **Project**: Music Maker (Mureka API 기반 AI 음원 생성 SaaS)
- **Codename**: mureka-studio
- **Stack**: Next.js 15 + FastAPI + Celery + PostgreSQL + Redis + MinIO/S3
- **Phase**: 풀 사이클 설계·구현 완료 → 실 API 연동 검증 중

---

## 1. 단계별 진행 (6 Step Full Cycle)

| Step | 영역 | 산출물 | 상태 | 주요 검증 |
|---|---|---|---|---|
| 1 | PRD | `docs/01-PRD.md` (425줄) | ✅ DONE | 페르소나 3, MoSCoW, 스토리 16, KPI 12, 리스크 8, 마일스톤 4단계 |
| 2 | UX 설계 | `docs/02-UX-Design.md` (690줄) | ✅ DONE | Mermaid 7개, 와이어프레임 W1~W6, 디자인 토큰, 반응형 6 breakpoint |
| 3 | 시스템 아키텍처 | `docs/03-Architecture.md` (1015줄) | ✅ DONE | ERD, API 명세 8개, 비동기 폴링 의사코드, Saga 크레딧 |
| 4 | FastAPI 백엔드 | `apps/api/` (69 파일) | ✅ DONE | **18/18 pytest 통과**, ruff 0 에러 |
| 5 | Next.js 프론트엔드 | `apps/web/` (70 파일) | ✅ DONE | Vitest 4 + Playwright E2E 140 (35×4 브라우저) |
| 6 | QA 슈트 | `docs/04-*.md`, E2E + Load + CI | ✅ DONE | 케이스 42개, locust + GitHub Actions, Makefile 통합 |
| 7 | 실 API 검증 | Mureka smoke + 응답 스키마 보강 | 🟡 BLOCKED | Mureka 계정 쿼터 소진 (HTTP 429) → 결제 대기 중 |

---

## 2. 핵심 산출물 위치

```
music-maker/
├── docs/                          ── 설계 문서 4종 (총 ~3.7k 줄)
│   ├── 01-PRD.md
│   ├── 02-UX-Design.md
│   ├── 03-Architecture.md
│   ├── 04-QA-Strategy.md
│   ├── 04-Test-Cases.md           42개 케이스 매트릭스
│   ├── 04-Manual-QA.md            릴리스 사인오프 시트
│   ├── PROGRESS.md                ★ 본 문서
│   └── adr/                       ADR-001~004 작성 완료
│       ├── ADR-001-async-worker-polling.md
│       ├── ADR-002-sse-vs-websocket.md
│       ├── ADR-003-credit-saga.md
│       └── ADR-004-mureka-response-abstraction.md
├── apps/
│   ├── api/                       FastAPI + Celery
│   │   ├── app/services/mureka_client.py     ★ Mureka 호환 레이어 (실제 응답 스키마 반영)
│   │   ├── app/workers/poll_task.py          5s 폴링, 최대 60회
│   │   ├── tests/                            18 pytest 통과
│   │   └── scripts/smoke_mureka.py           ★ 실 API 스모크 러너
│   └── web/                       Next.js 15 + shadcn/ui
│       └── tests/e2e/             5 spec, 140 시나리오
├── .github/workflows/ci.yml       7단계 CI
├── docker-compose.yml             postgres + redis + minio + api + worker
├── Makefile                       make dev / test / test-e2e / load / ci
└── README.md
```

---

## 3. 무엇이 작동하는가 (Verified)

### 3.1 백엔드 (apps/api)

- [x] **`make test` 통과** — `pytest tests/ -v` → 18 passed
- [x] Mureka 클라이언트 (httpx.AsyncClient, 재시도, 추상화)
  - 4xx → `MurekaPermanentError` (재시도 없음)
  - 429/5xx → `MurekaTransientError` (exp backoff 2회)
  - **실제 Mureka 응답 스키마 반영**:
    - `{"error":{"message":"..."}, "trace_id":"..."}` 파싱
    - `trace_id`를 body에서 추출 (헤더 없음 확인)
- [x] Celery 워커 폴링 (`poll_task.py`) — 5s × 60회, 완료 시 mp3 다운로드 + S3 업로드 + 크레딧 commit
- [x] Saga 크레딧 시스템 (hold → charge / refund, ledger 불변 로그)
- [x] SSE Hub (Redis pubsub `gen:{id}`)
- [x] RFC 7807 에러 + X-Trace-Id 미들웨어
- [x] Alembic 마이그레이션 1개 (`0001_initial.py`)

### 3.2 프론트엔드 (apps/web)

- [x] Next.js 15 App Router 빌드 (`.next/` 산출물 존재)
- [x] Studio 3-pane (W1) + 가사 에디터 (W2) + 스타일 프리셋 (W3) + 진행률 (W4) + A/B 비교 (W5) + 라이브러리 (W6)
- [x] wavesurfer.js 파형 + A/B 동기 재생
- [x] TanStack Query + Zustand 상태 관리
- [x] SSE 구독 + 폴링 fallback
- [x] MSW로 BE 미동작 시에도 자립 가능
- [x] Playwright 140 시나리오 작성 (실행은 브라우저 설치 후)

### 3.3 QA

- [x] CI 워크플로 (`.github/workflows/ci.yml`) — 7단계 (lint → unit → integration → e2e → build → deploy → smoke)
- [x] 부하 테스트 인프라 — `locustfile.py` + `mock_mureka_server.py` (외부 API 없이 5분 부하)
- [x] 수동 QA 체크리스트 (`docs/04-Manual-QA.md`)
- [x] 버그 트리아지 + Sentry 라우팅 규칙 (`04-QA-Strategy.md §5`)

### 3.4 실 API 검증 (Mureka)

- [x] **키 유효성 확인됨** — HTTP 429 응답 (인증은 통과, 잔여 쿼터만 소진)
- [x] **실제 응답 스키마 캡처** — `{"error":{"message":"You exceeded your current quota..."},"trace_id":"5fedd311..."}`
- [x] **응답 스키마에 맞춘 코드 보강 완료** — `_extract_error`, `_extract_trace_id` 헬퍼 추가
- [x] **회귀 테스트 4개 추가** — 실 응답 형태 검증
- [ ] 정상 가사 생성 (쿼터 충전 후)
- [ ] 정상 곡 생성 + 폴링 (쿼터 충전 후)

---

## 4. 무엇이 막혀 있는가 (Blocked / Pending)

### 4.1 🟡 Mureka 결제 대기

- **증상**: HTTP 429 `"You exceeded your current quota, please check your plan and billing details"`
- **원인**: Mureka 계정에 잔여 크레딧 0
- **사용자 액션 필요**: https://platform.mureka.ai/ → Billing → 플랜 구독 또는 크레딧 구매
- **결제 후 즉시 검증**:
  ```bash
  cd apps/api
  .venv/bin/python scripts/smoke_mureka.py            # 가사 (가장 저렴)
  .venv/bin/python scripts/smoke_mureka.py --song     # 가사 + 곡 (실 음원 발생)
  ```

### 4.2 ⚠ 후속 작업 (우선순위 순)

1. **결제 완료 후 풀 사이클 검증** — smoke 통과 → 응답 스키마 추가 보강 검토 → make load
2. ~~**ADR 4개 작성**~~ ✅ 완료 (2026-05-16) — `docs/adr/ADR-001~004`
3. **WAV 저장 지원** — 현재 MP3만, Mureka가 WAV URL 별도 반환 시 `_persist_songs` 확장
4. **next-auth 정식 OAuth** — 현재 credentials provider mock, Google OAuth 전환
5. **Stems / Billing / Share Link 라우터** — 모델만 존재, 라우터 미구현
6. **Idempotency-Key** (Arch §5.6) — 24h 중복 요청 차단
7. **로깅 마스킹 필터** — email/lyrics 본문 자동 마스킹 (현재 SecretStr만 의존)
8. **`apps/api/scripts/seed.py`** — Pro/Free 사용자 + 샘플 generation 시드

---

## 5. 알려진 한계 / 가정

| 영역 | 한계 |
|---|---|
| Mureka 응답 스키마 | 일부만 실제 캡처됨 (429 에러). succeeded/failed/running 상태별 응답은 미확인 |
| Playwright 실행 | 브라우저 미설치 (`pnpm exec playwright install` 1회 필요) |
| 부하 테스트 | `mock_mureka_server.py`는 in-memory (분산 부하엔 부적합) |
| 시드 데이터 | `apps/api/scripts/seed.py` 미작성 (E2E smoke 실행 시 사용자 수동 생성 필요) |
| 결제 (Stripe) | 키 미설정, 모델/라우터 스켈레톤만 존재 |

---

## 6. 다음 세션에서 가장 먼저 할 일

### 케이스 A: Mureka 결제 완료된 경우
```bash
cd apps/api
.venv/bin/python scripts/smoke_mureka.py
# 통과하면 곡 생성도 시도:
.venv/bin/python scripts/smoke_mureka.py --song
```
→ 응답 본문에서 새로운 필드/스키마가 발견되면 `_parse_items`, `_STATE_MAP`, 또는 `LyricsResult.raw` 활용 코드를 보강.

### 케이스 B: 결제 전이라면
1. ADR-001 ~ ADR-004 작성 (§4.2-2)
2. `apps/api/scripts/seed.py` 작성 (Pro/Free 사용자 + 샘플 generation)
3. `make test-e2e` 실행 (MSW 모킹으로 자립 가능)

### 케이스 C: 새 기능 추가 요청
- 우선 본 문서의 §3 (Verified)에서 해당 기능 베이스가 있는지 확인
- 없으면 `docs/03-Architecture.md` 의 ERD/API 명세를 변경한 뒤 backend-dev / frontend-dev 에이전트에 위임

---

## 7. 빠른 실행 명령 모음

```bash
# 인프라
make dev                     # docker-compose up
make down                    # docker-compose down

# 백엔드
cd apps/api && .venv/bin/python -m pytest tests/ -v        # 18 passed
make migrate                                                # alembic upgrade head

# 프론트엔드
cd apps/web && pnpm dev                                     # Next dev server
pnpm test                                                   # Vitest

# 통합
make test            # API + Web 단위
make test-e2e        # Playwright (브라우저 설치 후)
make load            # Locust 5분 (mock Mureka)
make ci              # 전체 파이프라인

# 실 Mureka API
cd apps/api && .venv/bin/python scripts/smoke_mureka.py [--song]
```

---

## 8. 변경 로그 (간단)

| 날짜 | 변경 |
|---|---|
| 2026-05-15 | Step 1~6 완료. PRD → UX → Arch → BE → FE → QA. |
| 2026-05-15 | 실 Mureka API 스모크 실행, 429로 키 유효성 확인. |
| 2026-05-15 | 실 응답 스키마(`{"error":{"message"},"trace_id"}`) 발견, `mureka_client.py` 보강. 회귀 테스트 4개 추가. 18/18 통과. |
| 2026-05-16 | PROGRESS.md 작성, music-maker-status 스킬 등록. |
| 2026-05-16 | ADR-001(폴링)·002(SSE)·003(크레딧 Saga)·004(Mureka 추상화) 4건 작성. |

---

## 9. 갱신 규칙 (LLM 행동 지침)

이 문서를 다음 시점에 **반드시** 갱신할 것:

- [ ] 새 Step/마일스톤이 완료될 때 → §1 매트릭스 + §8 변경 로그
- [ ] 새로운 막힘(blocker) 발생 시 → §4.1
- [ ] 사용자 액션이 필요한 항목 추가 시 → §4.1 또는 §4.2
- [ ] 검증된 새 기능 추가 시 → §3
- [ ] 명령어/스크립트가 추가/변경될 때 → §7

갱신은 `Edit` 도구로 surgical하게. 통째로 rewrite 금지.
