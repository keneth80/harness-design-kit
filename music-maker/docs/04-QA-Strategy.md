# 04-QA-Strategy: Music Maker — 통합 QA 전략

> 작성일: 2026-05-15
> 기반 문서: 01-PRD.md / 02-UX-Design.md / 03-Architecture.md
> 상태: Draft v0.1
> 핵심 원칙: **빠른 피드백 · 비용 의식 · 인간 검증은 마지막에**

---

## 0. QA 목표

| # | 목표 | 측정 |
|---|---|---|
| Q1 | PR 머지 전 회귀 결함 95% 이상 자동 검출 | CI 실패율 / 운영 핫픽스 빈도 |
| Q2 | Mureka API **실제 호출 없이** 99% 시나리오 검증 | 모킹 커버리지 |
| Q3 | 평균 PR 피드백 시간 ≤ 8분 | CI 평균 시간 |
| Q4 | 사용자 보고 결함의 70% 이상이 P3 이하 (사소함) | Sentry 심각도 분포 |
| Q5 | 접근성 WCAG 2.1 AA 위반 0건 | axe-core 자동 검사 |

---

## 1. 테스트 피라미드

### 1.1 비율 & 책임

```
                  ▲
                 / \         E2E (10%)
                /───\        - 핵심 사용자 플로우만
               /     \       - Playwright + MSW
              /───────\      Integration (30%)
             /         \     - 라우터↔DB↔Redis↔Worker
            /───────────\    - pytest + testcontainers
           /             \   Unit (60%)
          /───────────────\  - 순수 함수, 컴포넌트, 클라이언트 래퍼
         /─────────────────\ - pytest / vitest
```

| 레이어 | 비율 | 대상 | 도구 | 실행 시간 |
|---|---|---|---|---|
| **Unit** | 60% | 순수 함수, Mureka 클라이언트(모킹), Pydantic 검증, React 컴포넌트 | pytest, Vitest, RTL | < 30s |
| **Integration** | 30% | 라우터+DB+Redis, Celery 워커 (eager), SSE Hub | pytest + testcontainers / Postgres + Redis | < 3min |
| **E2E** | 10% | 사용자 플로우 (생성/실패/라이브러리/접근성) | Playwright + MSW | < 5min |
| **Load** | 별도 | 동시 10건 P95 검증 | Locust + mock_mureka | 5min on-demand |
| **Smoke** | 별도 | 실제 Mureka 1곡 검증 | Playwright `@smoke` | manual / nightly |

### 1.2 커버리지 목표

| 영역 | 목표 | 측정 도구 | 게이트 |
|---|---|---|---|
| `apps/api/app/services/` | 90%+ | pytest-cov | CI 차단 |
| `apps/api/app/routers/` | 85%+ | pytest-cov | CI 차단 |
| `apps/api/app/workers/` | 80%+ | pytest-cov | 경고 |
| `apps/api` 전체 | 75%+ | pytest-cov | CI 차단 |
| `apps/web/components/studio/` | 80%+ | Vitest | CI 차단 |
| `apps/web/lib/` | 85%+ | Vitest | CI 차단 |
| `apps/web` 전체 | 70%+ | Vitest | 경고 |

> **커버리지 ≠ 품질**. mutation testing(`mutmut`)을 v1.0에서 도입 검토.

---

## 2. Mureka API 의존성 처리 전략

Music Maker의 결정적 특수성: 외부 비동기 API에 의존하면서도 비용·속도·결정성을 모두 만족시켜야 한다.

### 2.1 4계층 모킹 전략

| 계층 | 사용처 | 구현 | Mureka 비용 |
|---|---|---|---|
| **L1. Pure Mock** | Unit (mureka_client) | `respx` / `httpx_mock` | 0원 |
| **L2. Local Stub Server** | Integration / Load | `mock_mureka_server.py` (aiohttp) | 0원 |
| **L3. MSW (Browser)** | E2E | `tests/mocks/handlers.ts` | 0원 |
| **L4. Real API** | Smoke / Production canary | `@smoke` 태그, `RUN_SMOKE=1` | 실제 과금 |

### 2.2 모킹 결정 트리

```
이 테스트는 무엇을 검증하나?
├── HTTP 직렬화/재시도/에러 매핑      → L1 (respx)
├── 라우터→DB→큐 통합 흐름            → L1 + L2 조합
├── 사용자 UI 시나리오                → L3 (MSW)
└── 실제 Mureka 응답 호환성           → L4 (Smoke, nightly)
```

### 2.3 응답 추상화 (회귀 방어선)

- `app/services/mureka_client.py` 의 `_parse_items()`, `_STATE_MAP`이 **유일한 호환 레이어**
- Mureka 응답 스키마 변경 시 이 두 함수만 수정 → 다른 테스트는 안정 유지
- 매주 1회 `@smoke` 야간 실행으로 스키마 드리프트 감지

### 2.4 실제 API 검증 정책

| 시점 | 호출 수 | 비용 통제 |
|---|---|---|
| Nightly smoke | 한/영 각 1곡 (총 2곡) | < $0.10/day |
| Release candidate | 5곡 (페르소나별 1곡) | < $0.50/release |
| Production canary | 0 (실 사용자 트래픽으로 대체) | 모니터링만 |

---

## 3. 레이어별 도구 & 기준

### 3.1 Backend (FastAPI + Celery)

| 종류 | 도구 | 특징 |
|---|---|---|
| Unit | `pytest`, `pytest-asyncio`, `respx`, `freezegun` | DB는 SQLite 호환 패치 (무인프라) |
| Integration | `pytest` + `testcontainers[postgresql,redis]` | 실제 Postgres 16 + Redis 7 |
| Worker | `celery` eager mode (`CELERY_TASK_ALWAYS_EAGER=True`) | 동기 실행으로 폴링 검증 |
| Load | `locust` | mock_mureka_server.py로 외부 호출 0 |
| 정적 분석 | `ruff`, `mypy --strict app/services` | 100% 통과 게이트 |

### 3.2 Frontend (Next.js)

| 종류 | 도구 | 특징 |
|---|---|---|
| Unit | `vitest`, `@testing-library/react`, `jsdom` | jsdom + happy-dom 혼용 |
| Mocking | `msw` (Service Worker) | Node + Browser 양쪽 |
| E2E | `playwright` (chromium/firefox/webkit + mobile-chrome) | MSW로 BE 모킹 |
| 접근성 | `@axe-core/playwright` | WCAG 2.1 AA |
| 시각 회귀 | (v1.5) Playwright snapshot | 미도입 |
| 정적 분석 | `eslint`, `tsc --noEmit` | 100% 통과 게이트 |

### 3.3 인프라 / CI

| 종류 | 도구 |
|---|---|
| CI | GitHub Actions (matrix: api/web 병렬) |
| 컨테이너 | docker buildx, multi-stage |
| 보안 | `gitleaks`, `trivy` (Docker 이미지) |
| 의존성 | `dependabot` weekly |

---

## 4. 우선순위 정의 (Priority)

| 우선순위 | 정의 | 응답 시간 | 자동화 |
|---|---|---|---|
| **P0** | 핵심 비즈니스 가치 직결, 1건 실패 시 출시 차단 | 즉시 | ✅ 필수 |
| **P1** | 주요 사용자 시나리오, 다수 사용자에 영향 | 24h | ✅ 권장 |
| **P2** | 부가 기능, 일부 사용자에 영향 | 1주 | △ 가능하면 |
| **P3** | UX 개선, 비주요 경로 | 백로그 | × 수동 OK |

---

## 5. 버그 심각도 정의 (Severity)

### 5.1 S1~S4 매트릭스

| 심각도 | 정의 | 예시 | SLA | 알림 채널 |
|---|---|---|---|---|
| **S1 Critical** | 서비스 사용 불가 또는 데이터 손실 | 결제 후 크레딧 미반영 / 전체 다운 / 보안 사고 | 즉시 (24/7) | PagerDuty + Slack #incident |
| **S2 High** | 핵심 기능 일부 불가, 우회 가능 | 특정 모델 생성 실패율 50%+ / SSE 연결 끊김 | 4시간 내 | Slack #alerts + 이메일 |
| **S3 Medium** | 부가 기능 결함, 단일 사용자 영향 | 즐겨찾기 토글 안 됨 / 한 페르소나만 영향 | 다음 영업일 | Slack #bugs |
| **S4 Low** | UI 사소함, 오타, 작은 일관성 문제 | 다크모드 컬러 어긋남 / 토스트 미표시 | 다음 스프린트 | GitHub Issues |

### 5.2 심각도 결정 매트릭스

```
                 영향 범위
                 ┌──────────┬──────────┬──────────┐
                 │ 1명      │ 일부      │ 다수     │
영향도           ├──────────┼──────────┼──────────┤
서비스 중단      │   S2     │   S1     │   S1     │
기능 사용 불가   │   S3     │   S2     │   S1     │
기능 오작동     │   S4     │   S3     │   S2     │
UI/UX 결함      │   S4     │   S4     │   S3     │
```

### 5.3 Sentry 알림 라우팅 규칙

```yaml
# Sentry → 라우팅
rules:
  - condition: "level:fatal OR tag:severity:S1"
    actions: [pagerduty, slack:#incident, email:on-call@]

  - condition: "tag:severity:S2 AND event.count > 5"
    actions: [slack:#alerts, email:team@]

  - condition: "tag:component:mureka_client AND status_code:5xx"
    actions: [slack:#alerts]

  - condition: "tag:component:billing"
    actions: [slack:#billing, email:finance@]

  - condition: "tag:severity:S3"
    actions: [slack:#bugs]
    # S4는 알림 없이 Sentry 대시보드만
```

### 5.4 자동 태그 매핑

| Sentry 이벤트 | 자동 부여 태그 |
|---|---|
| `exception.type == MurekaTimeoutError` | `component:mureka_client`, `severity:S2` |
| `exception.type == MurekaTransientError` | `component:mureka_client`, `severity:S3` |
| `status_code:402` | `component:billing`, `severity:S3` |
| `status_code:5xx` AND `path:/api/v1/songs` | `severity:S1` |
| Frontend Hydration Mismatch | `component:web`, `severity:S3` |

---

## 6. 회귀 테스트 자동화 정책

### 6.1 CI 파이프라인 게이트

```
PR 생성
   ├── 1. Lint (ruff + ESLint)          ── fail → PR 차단
   ├── 2. Typecheck (mypy + tsc)        ── fail → PR 차단
   ├── 3. Unit (pytest + Vitest)        ── fail → PR 차단
   ├── 4. Integration (testcontainers)  ── fail → PR 차단
   ├── 5. E2E (Playwright chromium)     ── fail → PR 차단
   └── 6. Build (Docker + Next build)   ── fail → PR 차단

main 머지
   ├── 7. Deploy staging                ── fail → 롤백
   └── 8. Smoke (@smoke, 실제 Mureka)   ── fail → 알림만, 차단 안 함
```

### 6.2 실행 시간 예산

| 단계 | 예산 | 초과 시 |
|---|---|---|
| Lint+Typecheck | 90s | 캐시 점검 |
| Unit | 60s | 분할 또는 병렬 |
| Integration | 180s | testcontainer 재사용 |
| E2E | 240s | 시나리오 슬림화 또는 병렬 |
| **PR 총합** | **8분 이내** | 알림 |

### 6.3 Flaky Test 정책

- 연속 3회 실패하지만 4회째 통과하는 테스트는 **flaky로 격리**
- `@flaky` 태그 부여 → 별도 잡에서 실행, PR 차단 미적용
- 1주일 내 안정화 또는 삭제 (책임자 지정)

---

## 7. 수동 QA 정책

### 7.1 자동 vs 수동 분리 기준

| 자동화 (CI) | 수동 검증 (릴리스 전) |
|---|---|
| 함수/컴포넌트 단위 행위 | **음질 청취 검증** |
| API 계약/응답 형식 | **다중 브라우저 시각 검증** |
| 데이터 흐름/SSE | **결제 실제 카드 입력 (테스트 모드)** |
| 접근성 (axe) | 보조기기 사용자 인터뷰 (분기 1회) |
| 회귀 시나리오 | 약관/저작권 문구 법무 검토 |

### 7.2 릴리스 전 게이트 (자세한 체크리스트는 `docs/04-Manual-QA.md`)

---

## 8. 테스트 데이터 관리

### 8.1 픽스처 전략

| 위치 | 픽스처 | 출처 |
|---|---|---|
| `apps/api/tests/fixtures/` | Mureka 응답 샘플 JSON (succeeded/preparing/running/failed) | 실제 응답 캡처 (실 API 호출 시) |
| `apps/web/tests/fixtures/` | UI 시나리오용 SongPublic 객체 | 수동 생성 |
| `apps/web/public/audio/sample.mp3` | wavesurfer 테스트용 작은 mp3 (1초) | 자체 제작 |

### 8.2 시드 데이터

- `apps/api/scripts/seed.py`: 로컬/스테이징용 사용자 3명 + 곡 10개 + 프리셋 3개
- 멱등성: 같은 시드 ID로 재실행 가능

---

## 9. 보안 테스트

| 항목 | 도구 | 빈도 |
|---|---|---|
| 시크릿 누출 검사 | `gitleaks` (pre-commit + CI) | 매 PR |
| Docker 이미지 취약점 | `trivy` | 매 build |
| 의존성 CVE | `pip-audit`, `pnpm audit` | weekly |
| API Key FE 노출 검증 | grep + 빌드 산출물 검사 (E2E TC-08) | 매 PR |
| OWASP Top 10 자동 검사 | (v1.0) `zap-baseline` | weekly staging |

---

## 10. 부하 & 성능 테스트

### 10.1 시나리오 (Locust)

- 가중치: 노래 생성 70% / 가사 생성 10% / 라이브러리 조회 20%
- 동시 사용자: 10, 50 (스트레스), 100 (한계)
- 실행 시간: 5분 (기본), 30분 (지속성 테스트)
- 외부 호출: `mock_mureka_server.py` 사용 (실 Mureka 0회)

### 10.2 합격 기준 (NFR 검증)

| 지표 | 목표 (NFR §6.1) | 측정 위치 |
|---|---|---|
| 동시 생성 | ≥ 10건 | Locust + Celery queue depth |
| P50 생성 시간 | ≤ 45초 | Locust |
| P95 생성 시간 | ≤ 60초 | Locust |
| API 응답 시간 (생성 시작) | P95 ≤ 500ms | Locust |
| 에러율 | < 0.5% | Locust |

---

## 11. 관측성 & 디버깅

### 11.1 테스트 실패 시 수집 정보

| 레이어 | 수집 데이터 |
|---|---|
| Unit | 실패 트레이스 + 입력 |
| Integration | + DB 스냅샷 + Redis 키 dump |
| E2E | + Playwright trace.zip + 영상 + 스크린샷 + console log + network HAR |
| Load | + Grafana 스크린샷 + 큐 깊이 시계열 |

### 11.2 운영 모니터링과 테스트 연계

- 운영 장애 발생 → `docs/error-log.md` 기록
- 동일 패턴 2회 재현 → 회귀 테스트 케이스로 승격 (`tests/regression/`)
- 학습된 교훈은 `docs/lessons-learned.md`

---

## 12. 다음 단계 체크리스트

- [ ] `docs/04-Test-Cases.md` 30+ 케이스 매트릭스 작성
- [ ] `docs/04-Manual-QA.md` 릴리스 전 체크리스트
- [ ] qa-tester 에이전트가 E2E + Load + CI 구현 (병렬 진행 중)
- [ ] Sentry 프로젝트 생성 + 라우팅 규칙 적용
- [ ] Codecov 연동 + 커버리지 PR 코멘트
- [ ] Playwright HTML 리포트 GitHub Pages 발행
- [ ] mutation testing (mutmut) v1.0 도입 검토

---

## 부록 A. 도구 버전 매트릭스

| 도구 | 버전 | 비고 |
|---|---|---|
| Python | 3.12 | uv |
| Node | 20 LTS | pnpm 9 |
| pytest | 8.x | |
| Vitest | 2.x | |
| Playwright | 1.49+ | chromium/firefox/webkit/mobile-chrome |
| Locust | 2.x | |
| testcontainers-python | 4.x | |
| MSW | 2.x | Service Worker + Node |
| axe-core | 4.x | via @axe-core/playwright |

## 부록 B. 용어

| 용어 | 의미 |
|---|---|
| **모킹 (Mocking)** | 외부 의존성을 가짜 응답으로 대체 |
| **스모크 테스트** | 실제 운영 환경에서 핵심 기능만 빠르게 검증 |
| **회귀 테스트** | 기존 기능이 깨지지 않는지 재검증 |
| **Flaky** | 같은 코드로 결과가 들쭉날쭉한 테스트 |
| **L1~L4** | 본 문서 §2.1의 모킹 계층 |
