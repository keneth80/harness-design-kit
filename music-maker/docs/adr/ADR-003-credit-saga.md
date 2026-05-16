# ADR-003: 크레딧 회계는 `credit_ledger`를 진실원으로 한 hold → charge/refund Saga로 구현한다

- **Status**: Accepted
- **Date**: 2026-05-16
- **Deciders**: backend, product
- **Related**: ADR-001 (워커 폴링), `docs/03-Architecture.md` §6

## 1. Context

곡 생성은 다음 4단계 분산 트랜잭션이다.

1. (API) 크레딧 차감
2. (Worker) Mureka 호출 + 폴링 (최대 5분)
3. (Worker) 결과 다운로드 + S3 업로드
4. (Worker) 곡 DB 기록

각 단계는 다른 프로세스에서 실행되며 실패할 수 있다. 다음 시나리오를 모두 안전하게 다뤄야 한다.

- **API 성공 / Worker 실패** → 사용자는 결과를 못 받았는데 크레딧이 빠지면 안 된다.
- **Mureka가 부분 실패** (1곡만 완료) → A/B 정책상 모두 실패로 간주, 환불.
- **이중 청구**: 같은 generation_id가 두 번 처리되더라도 크레딧이 두 번 차감되면 안 된다.
- **부하/관측성**: 사용자별 잔액 조회가 매 요청 발생 → O(1) 응답이어야 한다.
- **분쟁 대응**: "왜 내 크레딧이 줄었나?"에 대해 timestamp + 사유 + generation_id로 추적 가능해야 한다.

## 2. Decision

**Immutable append-only ledger (`credit_ledger`)** 를 진실원으로 하고, `users.credits` 컬럼은 **캐시된 스칼라**로 둔다. 트랜잭션 모델은 Saga의 단순 형태인 **hold → charge | refund**.

### 2.1 데이터 모델

`apps/api/app/models/credit_ledger.py`:

```
credit_ledger (
  id            UUID PK,
  user_id       UUID FK users,
  generation_id UUID FK generations NULL,
  type          ENUM(hold, charge, refund, grant, purchase),
  amount        INT,                  -- 부호 있음. hold/charge는 음수, refund/grant/purchase는 양수
  reason        VARCHAR(255),
  stripe_payment_intent VARCHAR NULL,
  created_at    TIMESTAMP
)
INDEX (user_id, created_at)
INDEX (generation_id)
```

**잔액 = `SUM(amount) WHERE user_id = ?`** — 항상 결정적이고, ledger를 변경 없이 재계산 가능.

### 2.2 상태 전이

```
[POST /songs]          [Worker 성공]              [Worker 실패]
    │                       │                          │
    ▼                       ▼                          ▼
+--------+              +---------+               +---------+
| hold   | ─ commit ──▶ | charge  |    refund ──▶ | refund  |
| -N     |              | 0       |               | +N      |
+--------+              +---------+               +---------+
```

- **hold**: API가 동기적으로 `-amount`를 insert (`credits.hold` in `apps/api/app/services/credits.py`). 잔액 부족 시 `InsufficientCreditsError` → HTTP 402.
- **charge**: Worker 성공 시 `amount=0`인 마커 row를 insert (`commit_sync`). 잔액은 그대로 — hold가 이미 차감했기 때문. 마커 row는 **감사 추적용**.
- **refund**: Worker 실패 시 `+amount` row를 insert (`refund_sync`). 잔액이 hold 이전으로 복원.

### 2.3 캐시 동기화

`users.credits`는 hold/refund/grant/purchase 시점에 같은 트랜잭션 내에서 업데이트. `commit`(charge)에는 변동 없으므로 미수정. **정합성 검증**: 정기 작업 (TBD) 또는 디버그 시 `SUM(ledger.amount) == users.credits` 확인.

### 2.4 멱등성

- API에서 `Generation` row를 먼저 `INSERT`(같은 트랜잭션) 한 뒤 `hold`에 `generation_id` FK로 연결. 이후 동일 generation에 대한 두 번째 hold는 새 generation_id가 필요하므로 자연스럽게 멱등.
- 워커 재시도 시 `Generation.status`로 `completed/failed`이면 early-return (`poll_task.py:114`) → charge/refund 중복 방지.
- 추가 보강책으로 `Idempotency-Key` HTTP 헤더 (Arch §5.6, `PROGRESS.md §4.2` 미구현).

## 3. Consequences

**Positive**

- ledger가 immutable → 회계 감사 / 분쟁 대응 / 재계산 가능.
- 트랜잭션 안전성: hold와 generation INSERT가 같은 DB 트랜잭션 → 부분 실패 없음.
- 워커가 죽어도 hold는 살아있으므로 refund 운영 작업이 가능.
- 잔액 조회는 인덱스된 SUM → 성능 충분 (사용자당 row 수 적음).

**Negative / Trade-offs**

- `users.credits`와 ledger SUM이 일시적으로 어긋날 수 있음 (드물지만 가능). 정기 reconciliation 잡 필요.
- charge 시 amount=0 row를 굳이 추가하므로 row 수가 약간 늘어남 (감사 가치로 정당화).
- ledger row 수가 무한 증가 → 1년 단위 archival/partition 전략 후속 검토.

**Risks**

- 워커가 charge 직전에 죽으면: generation은 `processing`인데 결과는 있다. → 별도 reaper가 hold 후 5분 이상 무진행이면 강제 refund 처리 (TBD).
- DB 트랜잭션 격리 수준 결함으로 동시 hold가 둘 다 통과하여 잔액 음수가 될 수 있음. → 현재 `READ COMMITTED` 가정. 동시성이 문제되면 `SELECT ... FOR UPDATE` 또는 advisory lock 도입.

## 4. Alternatives Considered

| 대안 | 기각 사유 |
|---|---|
| `users.credits` 단일 컬럼 + UPDATE | 감사 추적 불가, 분쟁 시 무력. 동시성 위험. |
| 외부 ledger 서비스 (Stripe, ledger-as-a-service) | 인프라 오버헤드, vendor lock-in, 결제는 별도 ADR 예정. |
| Two-phase commit (XA) | API와 Worker가 다른 프로세스 — XA 적용 비용 과대, 운영 부담. |
| Outbox 패턴만 사용 | 크레딧 무결성 보장에는 부족. 보조 수단으로는 검토 가능. |
| 양수 amount + `direction` 컬럼 | 잔액 계산이 CASE 식으로 복잡, 인덱스 활용 어려움. |

## 5. Implementation Refs

- `apps/api/app/models/credit_ledger.py` — 모델
- `apps/api/app/services/credits.py` — `hold`(async), `commit_sync`, `refund_sync`, `get_balance`
- `apps/api/app/routers/songs.py:113-119` — API hold 호출
- `apps/api/app/workers/poll_task.py:193-198` (commit), `:239-245` (refund) — Saga 매듭
- `docs/03-Architecture.md` §6 — 흐름도
- `apps/api/tests/` — 18 pytest 중 saga 관련 케이스
