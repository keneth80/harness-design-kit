# ADR-004: Mureka API 응답을 Pydantic 모델 + tolerant 파서로 추상화한다

- **Status**: Accepted
- **Date**: 2026-05-16
- **Deciders**: backend
- **Related**: ADR-001 (워커 폴링), `docs/03-Architecture.md` Appendix A

## 1. Context

Mureka 공개 문서는 다음 정보가 부족하다.

- 응답 필드의 정확한 이름 (`items` vs `songs` vs `results`?)
- `state` 문자열의 전체 enum 집합 (`running`/`processing`/`in_progress` 모두 관찰됨)
- 에러 본문 형태 (헤더 vs body, `error.message` vs `message`)
- `trace_id`가 헤더에 있는지 body에 있는지

2026-05 실 호출 결과, 다음과 같은 응답이 관찰되었다:

```
HTTP 429
Content-Type: application/json
{
  "error": { "message": "You exceeded your current quota, please check your plan and billing details" },
  "trace_id": "5fedd311..."
}
```

`x-trace-id` 헤더는 **없었고**, `trace_id`는 **body**에 있었다. (당초 헤더만 보던 코드는 trace 유실)

비즈니스 코드가 Mureka의 변덕에 직접 노출되면, 작은 wire 변경마다 광범위한 회귀가 발생한다.

## 2. Decision

`apps/api/app/services/mureka_client.py` 단일 파일이 Mureka의 모든 wire 포맷을 흡수한다. 외부 모든 호출자는 **Pydantic 모델**만 본다.

### 2.1 추상 계층

```
caller (router/worker)
   │  uses LyricsResult / TaskResponse / MurekaTaskStatus
   ▼
MurekaClient
   │  _parse_items, _normalise_state, _extract_error, _extract_trace_id
   ▼
httpx.AsyncClient  ⇄  Mureka HTTP API
```

### 2.2 핵심 파서들 (`mureka_client.py`)

| 함수 | 역할 |
|---|---|
| `_STATE_MAP` | `pending/preparing/queued/submitted/running/processing/in_progress/completed/succeeded/success/failed/error/cancelled` → 내부 4-state `pending/running/completed/failed`로 매핑 |
| `_normalise_state(v)` | 알 수 없는 값은 `"pending"`으로 안전 매핑 |
| `_parse_items(payload)` | `items`, `songs`, `results`, `variants` 키 중 첫 번째로 발견된 list 사용. 각 item에서 `url`/`audio_url`/`mp3_url` 등 다중 후보 시도. |
| `_extract_error(payload, status)` | `{"error":{"code","message"}}`, `{"error":"..."}`, `{"code","message"}` 세 가지 형태 모두 수용 |
| `_extract_trace_id(response, payload)` | 헤더 우선, body fallback (실 관찰 케이스 반영) |

### 2.3 모델

```python
LyricsResult     # POST /lyrics/generate
TaskResponse     # POST /song/generate 또는 /instrumental/generate (task_id만)
MurekaTaskItem   # 곡 1개 (URL, 메타데이터)
MurekaTaskStatus # GET /task/{id} 결과 (state, items, error, trace_id, raw)
```

모든 모델은 `raw: dict[str, Any]` 필드를 추가로 보관 — 신규 필드 발견 시 코드 변경 없이 캡처 가능.

### 2.4 재시도 / 에러 분류

```
4xx (429 제외)  → MurekaPermanentError   (재시도 없음, 호출자에게 즉시 전달)
429, 5xx        → MurekaTransientError    (exp backoff 2회)
TransportError  → MurekaTransientError    (exp backoff 2회)
business-level "failed" state → MurekaTaskFailed (워커가 환불 처리)
poll timeout    → MurekaTimeoutError      (워커가 환불 처리)
```

### 2.5 Boundary 원칙

> **Mureka의 wire 포맷이 바뀌면 오직 `_parse_*` 헬퍼와 Pydantic 모델만 수정한다.**
> router/worker는 절대 raw dict를 들여다보지 않는다.

## 3. Consequences

**Positive**

- Mureka 응답 변동에 강건. 회귀 비용 최소화.
- 모든 호출자는 강타입 (`MurekaTaskStatus.state` is `Literal[...]`) → IDE/타입체커가 분기 누락 발견.
- 테스트가 쉬움: `httpx.AsyncClient`를 `MockTransport`로 주입하고 wire-level fixture 응답으로 검증.
- `raw` 필드 보존 → 디버깅/추후 마이그레이션 시 원본 분석 가능.

**Negative / Trade-offs**

- "관용적 파서" 자체가 추가 코드 (≈ 100줄). 단, 한 곳에 집중되어 있어 인지 부담은 낮음.
- 새 wire 형태 발견 시 `_parse_*`를 사람이 직접 수정해야 함 — 자동 스키마 진화 아님.

**Risks**

- Mureka가 응답 스키마를 **호환되지 않게** 변경하면 (예: `state` 의미가 바뀜) 무음(silent) 매핑 오작동 가능. → `raw` 보존 + 회귀 테스트(`apps/api/tests/test_mureka_client_*.py`) 4개로 1차 방어. CI 알람 + smoke 잡으로 2차 방어.

## 4. Alternatives Considered

| 대안 | 기각 사유 |
|---|---|
| OpenAPI 자동 생성 클라이언트 | Mureka가 OpenAPI 스펙 미공개 |
| `requests` + dict 직접 사용 | 호출자가 매번 wire 포맷에 결합. 변경 비용 폭증. |
| TypedDict 기반 | runtime validation 없음. `raw` 보존 패턴 표현이 어색. |
| pydantic 1.x | 프로젝트는 pydantic 2 사용 중 (FastAPI/structlog 호환). |
| GraphQL 래퍼 | Mureka가 GraphQL이 아님 → 의미 없음. |

## 5. Implementation Refs

- `apps/api/app/services/mureka_client.py` — 본 ADR의 모든 결정이 구현된 파일 (헤드 docstring에 동일 내용 요약)
- `apps/api/app/core/exceptions.py` — `MurekaPermanentError`, `MurekaTransientError`, `MurekaTaskFailed`, `MurekaTimeoutError`
- `apps/api/scripts/smoke_mureka.py` — 실 API 호출용 스모크 러너
- `apps/api/tests/` — 회귀 4건: 실 응답 형태 (error.message, body trace_id, 429 분류) 검증
- `docs/03-Architecture.md` Appendix A — 관찰된 응답 캡처
- `docs/PROGRESS.md` §3.4 — Mureka 검증 현황

## 6. Observed Response Catalogue (캡처본)

> ⚠ 새로운 응답을 관찰할 때마다 이 섹션에 append. 코드 변경 단서.

**Case 1 — 429 quota exceeded (2026-05-15)**

```http
HTTP/1.1 429 Too Many Requests
content-type: application/json

{"error":{"message":"You exceeded your current quota, please check your plan and billing details"},"trace_id":"5fedd311..."}
```

→ 영향: `_extract_trace_id`가 body fallback을 갖도록 보강. `_extract_error`가 `error.message` 형태를 직접 지원.

**Case 2 — 정상 곡 생성 (TBD, 결제 완료 후)**

— pending —

**Case 3 — 정상 가사 생성 (TBD)**

— pending —

**Case 4 — failed task (TBD)**

— pending —
