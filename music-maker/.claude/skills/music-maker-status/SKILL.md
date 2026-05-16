---
name: music-maker-status
trigger: "어디까지|진행 상태|현재 상태|이어서|이어가|다음 작업|다음에 할|진행도|상황|어디 했|어디까지 했|where did we leave|where are we|status|progress|resume|continue|이전 작업|지난번"
---

# Music Maker — 진행 상태 스킬

이 프로젝트의 **단일 진실원(Source of Truth)**은 `docs/PROGRESS.md` 입니다.

## 1. 트리거 시 행동 (필수)

사용자가 "어디까지 했어?", "이어서 하자", "진행 상태", "다음 뭐 해?" 같은 질문을 하면:

1. **`docs/PROGRESS.md`를 먼저 읽는다** (Read 도구)
2. 다음 항목을 사용자에게 간결히 보고:
   - **Last updated 날짜**
   - **§1 단계별 진행 매트릭스** (✅/🟡/❌ 한눈에)
   - **§4.1 막혀 있는 항목** (사용자 액션 필요한 것)
   - **§6 다음 세션에서 가장 먼저 할 일** (현재 케이스에 맞는 것)
3. 보고는 표 1~2개 + 짧은 텍스트로. 전체 dump 금지.

## 2. 작업을 이어갈 때 (의미 있는 변화 후)

다음 시점에 **반드시** `docs/PROGRESS.md`를 갱신:

- 새 Step / 마일스톤 완료 → §1 매트릭스 + §8 변경 로그
- 새 blocker 발견 → §4.1
- 새 검증된 기능 → §3
- 새 명령어/스크립트 → §7

갱신은 **Edit 도구로 surgical하게** (통째로 rewrite 금지).
변경 로그(§8)에는 날짜 + 한 줄 요약.

## 3. 빠른 컨텍스트 회복용 핵심 정보

스킬이 로드되면 LLM이 다음을 즉시 알아야 함:

- **프로젝트**: Music Maker — Mureka API 기반 AI 음원 생성 SaaS
- **코드네임**: mureka-studio
- **스택**: Next.js 15 (apps/web) + FastAPI + Celery (apps/api) + PostgreSQL + Redis + MinIO
- **핵심 제약**:
  - Mureka API는 **비동기**(task_id 폴링, 5s × 60회 = 5분 타임아웃)
  - `MUREKA_API_KEY`는 **백엔드 전용** (FE 노출 절대 금지)
  - 크레딧 Saga: hold → charge / refund (credit_ledger가 진실원)
  - 1회 생성 = **A/B 2곡 반환**
- **설계 문서**:
  - `docs/01-PRD.md` — PRD
  - `docs/02-UX-Design.md` — 와이어프레임 W1~W6
  - `docs/03-Architecture.md` — ERD, API 명세, 비동기 워커
  - `docs/04-*.md` — QA (Strategy / Test-Cases / Manual-QA)

## 4. 자주 묻는 질문 빠른 답

| 사용자 질문 | 답 위치 |
|---|---|
| "테스트 어떻게 돌려?" | `PROGRESS.md §7` |
| "Mureka 키 어떻게 됐어?" | `PROGRESS.md §4.1` |
| "API 응답 어떻게 생겼지?" | `apps/api/app/services/mureka_client.py` 헤드 주석 + `_STATE_MAP` |
| "다음 우선순위?" | `PROGRESS.md §4.2` |
| "어디서 막혔지?" | `PROGRESS.md §4.1` |

## 5. 절대 하지 말 것

- ❌ `docs/PROGRESS.md`를 읽지 않고 "어디까지 했지" 류 질문 답변
- ❌ 통째로 rewrite (Edit으로 surgical하게)
- ❌ Mureka API 키를 응답/로그에 출력
- ❌ "전부 완료됐어요" 같은 추상적 답 — 항상 구체적 표·번호 인용
- ❌ 같은 정보를 매번 재요약 — `PROGRESS.md`에 한 번 기록하고 참조

## 6. 갱신 예시

작업이 진행됐을 때:
```
Edit docs/PROGRESS.md:
  - Last updated 날짜 변경
  - §1 해당 row의 상태 ✅로
  - §8 변경 로그에 한 줄 추가:
    "| 2026-05-XX | <한 줄 요약> |"
```

blocker 해소 시:
```
Edit docs/PROGRESS.md:
  - §4.1 항목 제거 또는 §3으로 이동
  - §8 변경 로그에 기록
```

---

**핵심 1줄**: "어디까지 했지?" → `docs/PROGRESS.md` 먼저 읽고, 구체적인 표/번호로 답하라.
