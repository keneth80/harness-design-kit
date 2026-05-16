# 04-Test-Cases: Music Maker — 테스트 시나리오 매트릭스

> 작성일: 2026-05-15
> 기반: `docs/04-QA-Strategy.md`
> 상태: Draft v0.1
> 총 케이스 수: **42개** (P0: 18 / P1: 16 / P2: 8)

---

## 사용 규칙

- **ID 체계**: `TC-NN`은 전 영역 통합 순번. 영역별 그룹은 색션으로 분리.
- **레이어**: U=Unit, I=Integration, E=E2E, L=Load, M=Manual
- **자동화**: ✅ = CI에서 자동 실행 / ⚠ = 작성됐으나 별도 트리거 / ❌ = 수동 전용
- **실행 위치**:
  - `apps/api/tests/{unit,integration,load}` (pytest / locust)
  - `apps/web/tests/{unit,e2e}` (Vitest / Playwright)
  - `docs/04-Manual-QA.md` (수동)

---

## 1. 가사 생성 (Lyrics) — 4개

| ID | 시나리오 | 우선순위 | 레이어 | 자동화 | 위치 |
|---|---|---|---|---|---|
| **TC-01** | 정상 프롬프트(한글, 주제+톤)로 가사 생성 → 구조 태그 포함하여 반환 | P0 | I | ✅ | `apps/api/tests/integration/test_routers_lyrics.py::test_generate_ok` |
| **TC-02** | 모더레이션 위반 입력(혐오 표현) → 422 + `moderation_blocked` | P0 | U+I | ✅ | `apps/api/tests/unit/test_moderation.py` + `test_routers_lyrics.py::test_blocked` |
| **TC-03** | Mureka 4xx (잘못된 prompt) → 즉시 fail, 재시도 없음 | P1 | U | ✅ | `test_mureka_client.py::test_lyrics_4xx_no_retry` |
| **TC-04** | 빈 prompt → 400 `invalid_prompt` | P1 | I | ✅ | `test_routers_lyrics.py::test_empty_prompt` |

### 검증 포인트

```
TC-01 기대:
  - response.status_code == 200
  - response.lyrics contains "[Verse" or "[Chorus"
  - response.moderation.flagged == False
  - response.credit_cost == 0   # 가사 생성은 무료
```

---

## 2. 음원 생성 (Song Generate) — 8개

| ID | 시나리오 | 우선순위 | 레이어 | 자동화 | 위치 |
|---|---|---|---|---|---|
| **TC-05** | 영문 가사 + R&B 스타일 + length=60s → 202 + generation_id | P0 | I | ✅ | `apps/api/tests/integration/test_routers_songs.py::test_create_en_rnb` |
| **TC-06** | 한글 가사 + K-Pop 스타일 + length=90s → 202 + generation_id | P0 | I | ✅ | `test_routers_songs.py::test_create_kr_kpop` |
| **TC-07** | 가사 없이 prompt만 (lyrics_mode=ai) → AI 가사 자동 채움 후 생성 | P0 | I | ✅ | `test_routers_songs.py::test_create_ai_lyrics` |
| **TC-08** | 인스트루멘탈 모드 (mode=instrumental) → 보컬 없이 생성 요청 | P0 | I | ✅ | `test_routers_songs.py::test_create_instrumental` |
| **TC-09** | 1회 호출이 **A/B 2곡** 반환 → variant=A,B 두 행 INSERT | P0 | I | ✅ | `test_worker_poll.py::test_two_variants_persisted` |
| **TC-10** | 모델 명시(model=mureka-7) 시 Mureka 호출 파라미터에 포함 | P1 | U | ✅ | `test_mureka_client.py::test_model_param` |
| **TC-11** | 모델 미명시(auto) 시 기본값으로 호출 | P2 | U | ✅ | `test_mureka_client.py::test_model_auto` |
| **TC-12** | length_s > 300 → 422 (NFR 5분 제한) | P0 | I | ✅ | `test_routers_songs.py::test_length_over_limit` |

---

## 3. 비동기 폴링 (Async Polling) — 6개

| ID | 시나리오 | 우선순위 | 레이어 | 자동화 | 위치 |
|---|---|---|---|---|---|
| **TC-13** | Mureka가 task_id 반환 → 워커가 5초 간격 폴링 → completed 수신 후 DB 업데이트 | P0 | I | ✅ | `test_worker_poll.py::test_polling_until_completed` |
| **TC-14** | 폴링 도중 progress 단계마다 Redis pub/sub publish 호출 | P0 | I | ✅ | `test_worker_poll.py::test_sse_publishes_progress` |
| **TC-15** | Mureka 응답에서 mp3 URL → MinIO/S3에 업로드, songs.storage_key 저장 | P0 | I | ✅ | `test_worker_poll.py::test_audio_uploaded` |
| **TC-16** | 5분 (60회) 초과 → MurekaTimeoutError → 환불 + status=failed | P0 | I | ✅ | `test_worker_poll.py::test_timeout_refund` |
| **TC-17** | preparing → running → succeeded 상태 매핑 정확성 | P1 | U | ✅ | `test_mureka_client.py::test_state_mapping` |
| **TC-18** | Mureka 응답 형태 변경(필드 누락) → `_parse_items` 안전한 폴백 | P1 | U | ✅ | `test_mureka_client.py::test_parse_resilience` |

### 검증 포인트 (TC-13)

```python
def test_polling_until_completed(celery_eager, mureka_mock, db):
    # given: Mureka가 3회째 polling에서 completed 반환
    mureka_mock.task_responses(["preparing", "running", "completed_with_2_items"])

    # when: 워커 실행
    poll_mureka_task(generation_id)

    # then:
    assert db.get(Generation, generation_id).status == "completed"
    assert db.query(Song).filter_by(generation_id=generation_id).count() == 2
    assert mureka_mock.poll_count == 3
```

---

## 4. 실패 & 재시도 & 환불 — 5개

| ID | 시나리오 | 우선순위 | 레이어 | 자동화 | 위치 |
|---|---|---|---|---|---|
| **TC-19** | Mureka 5xx → exponential backoff 재시도 2회 → 그래도 실패 시 크레딧 환불 | P0 | U+I | ✅ | `test_mureka_client.py::test_5xx_retry` + `test_worker_poll.py::test_failure_refund` |
| **TC-20** | Mureka task.failed → 1회 재시도 → 환불 | P0 | I | ✅ | `test_worker_poll.py::test_task_failed_refund` |
| **TC-21** | 4xx(입력 오류) → 즉시 fail, 재시도 없음 | P0 | U | ✅ | `test_mureka_client.py::test_4xx_no_retry` |
| **TC-22** | 환불 후 credit_ledger에 type=refund 행 추가, users.credits 캐시 갱신 | P0 | I | ✅ | `test_credits.py::test_refund_ledger` |
| **TC-23** | 멱등성(Idempotency-Key) — 동일 키 24h 내 재요청 → 같은 generation_id | P1 | I | ⚠ | `test_routers_songs.py::test_idempotency` (TODO) |

---

## 5. 동시성 & Rate Limiting — 3개

| ID | 시나리오 | 우선순위 | 레이어 | 자동화 | 위치 |
|---|---|---|---|---|---|
| **TC-24** | 동일 사용자 11번째 생성 요청(시간당) → 429 `rate_limit_exceeded` | P1 | I | ✅ | `test_routers_songs.py::test_rate_limit_per_hour` |
| **TC-25** | 동시 10건 요청 → 모두 큐 적재 + Mureka 동시 호출 ≤ worker concurrency | P0 | L | ⚠ | `apps/api/tests/load/locustfile.py::ConcurrentGenerate` |
| **TC-26** | 무료 플랜 일 5건 초과 → 429 + 업그레이드 유도 | P2 | I | ✅ | `test_routers_songs.py::test_free_plan_daily_cap` |

---

## 6. 권한 & 보안 — 4개

| ID | 시나리오 | 우선순위 | 레이어 | 자동화 | 위치 |
|---|---|---|---|---|---|
| **TC-27** | 타 사용자의 generation 조회 → 403/404 | P0 | I | ✅ | `test_routers_songs.py::test_other_user_forbidden` |
| **TC-28** | MUREKA_API_KEY가 빌드 산출물/응답/로그에 포함되지 않음 | P0 | E+U | ✅ | `apps/web/tests/e2e/accessibility.spec.ts::api_key_not_leaked` + `apps/api/tests/unit/test_logging.py::test_no_secret` |
| **TC-29** | JWT 없이 보호 엔드포인트 호출 → 401 | P0 | I | ✅ | `test_routers_songs.py::test_no_jwt` |
| **TC-30** | 공유 링크 토큰(share_token) → 비로그인 read-only 접근 가능 | P2 | I | ⚠ | `test_projects.py::test_share_token` (TODO) |

### 검증 포인트 (TC-28)

```typescript
// apps/web/tests/e2e/accessibility.spec.ts
test('@p0 API_KEY가 클라이언트 번들에 누출되지 않음', async ({ page }) => {
  const response = await page.goto('/studio')
  const html = await page.content()
  const scripts = await page.locator('script').allTextContents()

  expect(html).not.toMatch(/mk_[A-Za-z0-9]{20,}/)
  scripts.forEach(s => expect(s).not.toMatch(/MUREKA_API_KEY/i))
})
```

---

## 7. 크레딧 시스템 (Saga) — 3개

| ID | 시나리오 | 우선순위 | 레이어 | 자동화 | 위치 |
|---|---|---|---|---|---|
| **TC-31** | 잔액 부족 시 생성 요청 → 402 `insufficient_credits` | P0 | I | ✅ | `test_routers_songs.py::test_insufficient_credits` |
| **TC-32** | hold → 성공 시 charge로 정산, 실패 시 refund로 복구 | P0 | I | ✅ | `test_credits.py::test_saga_commit_and_refund` |
| **TC-33** | `users.credits` 캐시와 `SUM(credit_ledger.amount)` 일치 | P1 | I | ✅ | `test_credits.py::test_balance_invariant` |

---

## 8. 라이브러리 & 다운로드 — 4개

| ID | 시나리오 | 우선순위 | 레이어 | 자동화 | 위치 |
|---|---|---|---|---|---|
| **TC-34** | 라이브러리 페이징(커서) → 무한 스크롤 정확성 | P1 | E | ✅ | `apps/web/tests/e2e/library.spec.ts::pagination` |
| **TC-35** | 장르/즐겨찾기/프로젝트 필터 조합 → 결과 갱신 | P1 | E | ✅ | `library.spec.ts::filter_combo` |
| **TC-36** | MP3/WAV 다운로드 → 서명 URL 만료 5분 | P1 | I | ✅ | `test_library.py::test_signed_url_ttl` |
| **TC-37** | 다중 선택 → ZIP 일괄 다운로드 | P2 | E | ✅ | `library.spec.ts::bulk_zip` |

---

## 9. UI 상태 & 사용성 — 5개

| ID | 시나리오 | 우선순위 | 레이어 | 자동화 | 위치 |
|---|---|---|---|---|---|
| **TC-38** | 생성 중 페이지 새로고침 → Zustand 복구 + SSE 재구독 + 진행률 이어보임 | P1 | E | ✅ | `apps/web/tests/e2e/generate-song.spec.ts::resume_after_reload` |
| **TC-39** | SSE 연결 끊김 → 5초 폴링 fallback으로 상태 복구 | P1 | E | ✅ | `generate-failure.spec.ts::sse_disconnect_fallback` |
| **TC-40** | A/B 동기 재생 토글 → 같은 시점에서 cross-fade | P1 | U | ✅ | `apps/web/tests/unit/waveform-player.test.tsx::ab_sync` |
| **TC-41** | 키보드 단축키 — Cmd+Enter=생성, Space=재생/정지 | P1 | E | ✅ | `accessibility.spec.ts::keyboard_shortcuts` |
| **TC-42** | `prefers-reduced-motion` ON → 파동/회전 애니메이션 disable | P2 | E | ✅ | `accessibility.spec.ts::reduced_motion` |

---

## 10. 접근성 (a11y) — 별도 검증

| 페이지 | axe-core 위반 허용 | 키보드 도달 | 스크린리더 |
|---|---|---|---|
| `/` (랜딩) | 0 | ✅ | ✅ |
| `/studio` | 0 | ✅ | WaveformPlayer aria-* |
| `/library` | 0 | ✅ | ✅ |
| `/studio/result/[id]` | 0 | ✅ | ✅ |
| `/settings` | 0 | ✅ | ✅ |

→ `apps/web/tests/e2e/accessibility.spec.ts` 가 5개 페이지를 순회 검사.

---

## 11. 우선순위 & 자동화 통계

### 11.1 우선순위 분포

| P0 | P1 | P2 | 합 |
|---|---|---|---|
| 18 | 16 | 8 | **42** |

### 11.2 레이어 분포

| Unit | Integration | E2E | Load | Manual |
|---|---|---|---|---|
| 9 | 22 | 9 | 1 | (별도 `04-Manual-QA.md`) |

### 11.3 자동화 비율

| 자동화 ✅ | 작성 예정 ⚠ | 수동 ❌ |
|---|---|---|
| 39 (93%) | 3 (TC-23, TC-25, TC-30) | 0 |

---

## 12. 실행 명령어

```bash
# 전체 자동 테스트
make test                  # API + Web 단위/통합 (5초)
make test-e2e              # Playwright E2E (4분)
make test-a11y             # 접근성 전용 (1분)
make load                  # Locust 5분

# 우선순위별
cd apps/web && pnpm playwright test --grep @p0
cd apps/api && pytest -m p0

# 실제 Mureka API (smoke)
make test-e2e-smoke        # RUN_SMOKE=1, 야간/릴리스 시
```

---

## 13. 케이스 추가 가이드

새 결함이 운영에서 발견되면:

1. `docs/error-log.md` 기록
2. 재현 테스트 작성 → 이 매트릭스에 `TC-NN` 추가
3. 동일 패턴 2회 발생 시 `docs/lessons-learned.md` 승격
4. CI에 통합 (회귀 방지)

---

## 부록 A. 매핑: PRD KPI ↔ Test Case

| PRD KPI (§5) | 검증 TC |
|---|---|
| 생성 성공률 ≥ 95% | TC-13, TC-19, TC-20 |
| P50 ≤ 45초 | TC-25 (Load) |
| 동시 생성 10건 | TC-25 |
| 5분 길이 제한 | TC-12 |
| 콘텐츠 모더레이션 | TC-02 |

## 부록 B. 매핑: PRD Risk ↔ Test Case

| Risk (§7) | 완화 TC |
|---|---|
| R1 API 비용 폭증 | TC-24, TC-26 |
| R3 콘텐츠 모더레이션 | TC-02 |
| R4 Mureka API 장애 | TC-19, TC-20, TC-39 |
