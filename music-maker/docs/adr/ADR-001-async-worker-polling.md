# ADR-001: Mureka 작업 처리를 Celery 워커 + 5초 폴링 모델로 한다

- **Status**: Accepted
- **Date**: 2026-05-16
- **Deciders**: backend, infra
- **Supersedes**: —
- **Related**: ADR-002 (SSE), ADR-004 (Mureka 응답 추상화), `docs/03-Architecture.md` §5.2

## 1. Context

Mureka의 `/song/generate`는 **비동기 작업**이다. 호출 즉시 `task_id`만 반환되고, 실제 곡은 백엔드가 `/task/{id}`를 폴링해서 받아와야 한다. 한 곡 생성은 평균 30~90초, 최대 5분까지 걸린다.

FastAPI 요청 핸들러는 다음 제약을 갖는다:

- HTTP 요청을 5분간 잡고 있으면 reverse proxy/CDN 타임아웃에 걸린다.
- 멀티 워커 환경에서 단일 요청이 워커 슬롯을 5분간 점유하면 동시 처리량이 급감한다.
- 사용자는 진행률(progress)을 실시간으로 보고 싶어한다 — 단순 fire-and-forget로는 부족하다.
- 실패 시 **크레딧 환불**이 일관되게 일어나야 한다 (Saga, ADR-003).

## 2. Decision

**Celery + Redis broker** 기반의 백그라운드 워커가 Mureka 작업을 처리한다.

- `POST /api/v1/songs` 핸들러는 DB row(`generations`)를 만들고 크레딧을 hold한 뒤 `run_generation.delay(generation_id)`만 호출하고 **즉시 202 Accepted**를 반환한다.
- 워커는 다음 4단계를 순차 실행한다 (`apps/api/app/workers/poll_task.py`):
  1. `MurekaClient.generate_song(...)` 호출 → `task_id` 확보
  2. **5초 간격으로 최대 60회 폴링** (`mureka_poll_interval_s=5`, `mureka_poll_max_count=60` → 총 5분 타임아웃)
  3. `state=="completed"`이면 mp3 다운로드 후 S3/MinIO 업로드
  4. 결과 commit (`Song` row 생성, 크레딧 charge, generation 상태 `completed`)
- 진행률은 폴링 iteration마다 `progress = min(10 + i*1.5, 95)`로 보정하여 `gen:{id}` 채널에 SSE 이벤트 발행.
- **Transient 실패** (`429`, `5xx`, transport error, `MurekaTimeoutError`) → Celery `self.retry`로 최대 2회 재시도 (exp backoff: 2s, 4s).
- **Permanent 실패** (`4xx` 외 다른 비즈니스 거부) 및 재시도 소진 → 크레딧 환불 + `generation.status=failed`.

폴링 주기/회수는 `Settings`로 외부화하여 production tuning이 가능하다 (`apps/api/app/config.py`).

## 3. Consequences

**Positive**

- API 응답 즉시 종료 → 워커 슬롯 점유 시간 ms 단위.
- 워커는 수평 확장 가능 (Celery worker 수만 늘리면 됨).
- 폴링 로직 한 곳(`poll_task.py`)에만 존재 → 디버깅 용이.
- DB의 `generations.status`가 단일 진실원이므로 SSE/HTTP 폴 양쪽 모두 정합성 유지.

**Negative / Trade-offs**

- 5초 폴링은 최악의 경우 5초만큼 응답이 지연된다. 사용자 체감 progress가 톱니파처럼 보일 수 있다 → 클라이언트 측에서 보간 처리(`apps/web`).
- Mureka 측이 webhook을 지원할 경우 폴링은 비효율 → 그러나 현재 공개 API에 webhook 명세 없음.
- Celery 의존성 추가 → `redis` 컨테이너 필수 (이미 SSE/캐시용으로 사용 중이라 비용 동일).

**Risks**

- Celery worker가 Mureka 응답을 5분 안에 못 받으면 강제 timeout — `MurekaTimeoutError` 던지고 환불. 환불 누락 방지는 ADR-003 참고.
- 워커 프로세스가 중간에 죽으면 `generation.status`가 `processing`인 채로 남는다 → 별도 reaper/주기적 cleanup이 추후 필요 (현재 미구현, `PROGRESS.md §4.2`).

## 4. Alternatives Considered

| 대안 | 기각 사유 |
|---|---|
| HTTP long polling (요청 1개로 5분 대기) | 워커 슬롯 점유, CDN/Proxy 타임아웃 |
| Mureka webhook | API에 webhook 명세 없음 |
| AWS Step Functions / Temporal | 인프라 비용 과대, MVP에 불필요 |
| FastAPI BackgroundTasks | 같은 프로세스 내 실행 → 멀티 worker 안전 X, 재시도 없음 |
| asyncio.create_task in API process | 위와 동일 + 프로세스 재시작 시 작업 손실 |

## 5. Implementation Refs

- `apps/api/app/workers/poll_task.py` — 메인 task `run_generation`
- `apps/api/app/workers/celery_app.py` — Celery app 정의
- `apps/api/app/services/mureka_client.py` — `query_task()` 폴링 메서드 (ADR-004)
- `apps/api/app/routers/songs.py:49-56` — `_enqueue()` 호출부
- `docs/03-Architecture.md` §5.2 — 시퀀스 다이어그램
