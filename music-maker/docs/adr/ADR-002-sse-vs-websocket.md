# ADR-002: 진행률 실시간 전달은 WebSocket이 아닌 SSE(Server-Sent Events)를 사용한다

- **Status**: Accepted
- **Date**: 2026-05-16
- **Deciders**: backend, frontend
- **Related**: ADR-001 (Celery 폴링), `docs/03-Architecture.md` §5.3

## 1. Context

ADR-001의 결과로, 워커가 곡 생성 진행 상황을 클라이언트에 통보해야 한다. 통신 요구사항은 다음과 같다:

- 방향: **서버 → 클라이언트 단방향**. 클라이언트는 별도 HTTP API로 명령을 보낸다.
- 빈도: 진행률 이벤트 ~3-5회 + 최종 `completed`/`failed` 1회. 평균 트래픽 ≤ 10 msg/conn.
- 연결 수명: 30초~5분.
- **인증 필요**: 본인 generation만 구독 가능.
- 백엔드 워커(별도 Celery 프로세스)에서 API 프로세스로 이벤트가 흘러들어와야 한다.
- 브라우저 호환성 / CORS / proxy 대응 필요.

## 2. Decision

**SSE (Server-Sent Events) + Redis Pub/Sub bridge**를 사용한다.

- 엔드포인트: `GET /api/v1/songs/{generation_id}/stream` (`apps/api/app/routers/songs.py:170`).
- 응답 MIME: `text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- 워커는 Redis 채널 `gen:{generation_id}`에 JSON 메시지를 publish (`publish_sync` in `apps/api/app/services/sse_hub.py`).
- API 프로세스는 같은 채널을 subscribe하여 클라이언트에게 `data: <json>\n\n` 형식으로 흘려보낸다.
- **25초 keep-alive ping** (`data: {"event":"ping"}`) — proxy idle timeout 회피.
- `event in ("completed","failed")` 수신 시 연결 종료.
- 인증은 표준 FastAPI dependency (`get_current_user`)를 그대로 사용 — SSE는 일반 HTTP이므로 쿠키/Bearer 모두 그대로 작동.

클라이언트(`apps/web`)는 `EventSource` API를 사용하며, SSE 끊김 시 **HTTP 폴링 fallback** (`GET /api/v1/songs/{id}` 1~2초 간격)을 한다.

## 3. Consequences

**Positive**

- HTTP 기반이라 인증/로깅/CORS/Proxy 처리가 기존 미들웨어와 동일.
- 단방향이라 프로토콜 표면이 좁다 — 보안 검토 비용 ↓.
- 브라우저 `EventSource`는 **자동 재연결**을 내장 → 클라이언트 로직 단순화.
- Redis Pub/Sub로 워커-API 디커플링: 워커는 어느 API 인스턴스가 구독 중인지 몰라도 됨.
- 단일 generation에 다중 탭/디바이스가 동시에 구독해도 fan-out 비용 무시 가능.

**Negative / Trade-offs**

- HTTP/1.1에서 한 도메인당 동시 연결 6개 제한 — 한 사용자가 6개 이상 generation을 동시에 구독하면 큐잉됨. HTTP/2로 완화 가능. MVP 범위에서는 비문제.
- IE/old Edge 미지원 — 본 프로젝트는 modern 브라우저 타깃이므로 무영향.
- 메시지 손실 방지 보장이 약함: Redis Pub/Sub는 fire-and-forget. 구독 시점 이전 메시지는 유실. → `GET /api/v1/songs/{id}` 폴링 fallback이 이 갭을 메운다.

**Risks**

- 일부 corporate proxy가 streaming response를 버퍼링할 수 있음 → `X-Accel-Buffering: no` 헤더로 nginx/ingress 단에서 비활성화. 그래도 막히면 클라이언트가 폴링으로 자동 전환.
- Redis 장애 시 SSE 끊김 → 폴링 fallback이 동작하므로 사용자 경험 degraded but not broken.

## 4. Alternatives Considered

| 대안 | 기각 사유 |
|---|---|
| **WebSocket** | 양방향 필요 없음. 인증/재연결/heartbeat을 직접 구현해야 함. ASGI 미들웨어와 통합 비용 ↑. |
| **HTTP long polling만** | 진행률 표시 지연 ≥ 폴 interval, 클라이언트 코드 복잡, 서버 부하 ↑. (단, **fallback 용도로는 유지**) |
| **gRPC / gRPC-Web** | 인프라 오버헤드 과대, MVP 부적합. |
| **Firebase Realtime / Supabase Realtime** | 외부 의존성 추가, 데이터 거버넌스 복잡. |
| **MQTT over WebSocket** | 단방향 알림에 과한 스택. |

## 5. Implementation Refs

- `apps/api/app/services/sse_hub.py` — `publish_sync`, `publish_async`, `subscribe` (Redis 브리지)
- `apps/api/app/routers/songs.py:170-205` — `stream_generation` 엔드포인트
- `apps/api/app/workers/poll_task.py:53-59` — 워커 `_publish` helper
- `apps/web/` — `EventSource` 클라이언트 + 폴링 fallback
- `docs/03-Architecture.md` §5.3 — 시퀀스 다이어그램
