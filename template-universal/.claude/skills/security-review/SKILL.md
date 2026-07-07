---
name: security-review
trigger: "보안 리뷰|보안 점검|취약점 점검|RLS 점검|권한 검증|security review|IDOR"
---

# Security Review

**언제 쓰나:** 기능 구현 후·배포 전에 논리적 취약점(권한 검증 누락, IDOR)과 스택 특화 설정 실수를 점검할 때.
secret_scan 훅(시크릿 유출)·security_gate 훅(위험 명령)이 **기계적으로 잡는 것 바깥**의,
"코드는 돌아가지만 권한 모델이 뚫려 있는" 종류의 결함이 이 스킬의 대상이다.
`/security-review` 커맨드가 security-reviewer 에이전트와 함께 이 문서를 사용한다.

## 방법론: 논리 취약점 (스택 무관)

### 1. 권한 매트릭스부터
코드를 읽기 전에 표를 만든다: 행=리소스(엔드포인트/테이블/액션), 열=역할(비로그인/일반/소유자/관리자).
각 칸에 "허용되어야 하는가"를 채우고, 그 다음에 코드가 실제로 그렇게 강제하는지 대조한다.
매트릭스 없이 코드부터 읽으면 "인증은 있는데 인가가 없는" 구멍을 놓친다.

### 2. IDOR (Insecure Direct Object Reference)
ID를 받는 모든 지점에서 물어라: **"이 ID가 요청자 소유인지 서버가 확인하는가?"**
- `GET /orders/{id}` — 인증만 확인하고 `order.user_id == current_user.id` 대조가 없으면 IDOR.
- 목록 API가 필터 없이 전체를 주고 프론트에서 걸러내는 패턴 — 프론트 필터는 보안이 아니다.
- UUID라서 추측 불가능하다는 방어는 인정하지 않는다(로그·공유 URL로 유출됨).

### 3. 인가 검증의 위치
- 인가는 **데이터에 가장 가까운 층**에서 강제되어야 한다(DB RLS > 서비스 레이어 > 라우터 > 프론트).
- 프론트엔드의 버튼 숨김·라우트 가드는 UX이지 보안이 아니다. 반드시 서버 측 대응물이 있는지 확인.
- 미들웨어 인증 후 핸들러가 역할(role)을 다시 확인하는지 — "로그인했으니 관리자 API도 통과" 패턴 주의.

### 4. 상태 변경 연산의 검증
- 클라이언트가 보낸 가격·수량·역할·user_id 필드를 서버가 그대로 신뢰하는가 (mass assignment).
- 멱등성 없는 중요 연산(포인트 지급, 결제)의 중복 요청 처리.

## 스택 특화 체크리스트

### Supabase
- [ ] **모든 public 스키마 테이블에 RLS 활성화** — `alter table X enable row level security;` 누락 테이블은 anon 키로 전체 접근 가능. `select relname from pg_class where relrowsecurity = false` 로 점검.
- [ ] **정책이 4개 연산별로 존재** — select/insert/update/delete 각각. select 정책만 만들고 update를 잊는 실수가 흔함.
- [ ] **`service_role` 키는 서버 전용** — 클라이언트 번들(`NEXT_PUBLIC_*`, 프론트 코드)에 절대 금지. RLS를 전부 우회한다. (유출 자체는 secret_scan 훅이 잡지만, 서버 코드에서의 오남용 — 사용자 요청 처리에 service_role 클라이언트를 쓰면서 수동 권한 확인이 없는 경우 — 는 여기서 본다.)
- [ ] **RLS 정책 내 `auth.uid()` 사용 확인** — `using (true)`는 사실상 무방비. `user_id = auth.uid()` 형태인지.
- [ ] **Storage 버킷 정책** — 테이블 RLS와 별개다. 비공개 파일 버킷에 정책이 있는지.
- [ ] **DB 함수 `security definer`** — RLS를 우회하므로 내부에서 자체 권한 확인 필수. `search_path` 고정 여부도 확인.

### Next.js
- [ ] **Server Action은 public 엔드포인트다** — `"use server"` 함수는 UI에서 안 보여도 직접 호출 가능. 모든 액션 첫 줄에서 세션 확인 + 입력을 zod 등으로 파싱하는지.
- [ ] **미들웨어 인증에만 의존 금지** — 미들웨어는 우회 사례(CVE-2025-29927 등)가 있었다. 페이지/핸들러/액션에서 재검증.
- [ ] **`NEXT_PUBLIC_` 접두사 점검** — 이 접두사가 붙으면 번들에 포함된다. 서버 전용 값에 붙어 있지 않은지.
- [ ] **Route Handler(`app/api/**`)마다 인증·인가** — 페이지에 가드가 있어도 API는 별개.
- [ ] **서버 컴포넌트에서 클라이언트로 넘기는 props** — 민감 필드(email, 내부 ID, 토큰)가 통째로 직렬화되지 않는지.

### FastAPI
- [ ] **인증은 `Depends`로 강제** — 데코레이터 없는 "문서에만 없는" 엔드포인트도 라우터에 등록되면 열려 있다. 라우터 전수 조사.
- [ ] **소유권 확인이 쿼리에 포함** — `where id = :id` 가 아니라 `where id = :id and user_id = :uid`.
- [ ] **응답 모델로 필드 제한** — `response_model=` 없이 ORM 객체를 그대로 반환하면 해시·내부 플래그가 새어 나간다.
- [ ] **Pydantic 모델에 여분 필드 거부** — `model_config = ConfigDict(extra="forbid")` 또는 화이트리스트. role/is_admin 주입 방지.
- [ ] **CORS `allow_origins=["*"]` + `allow_credentials=True` 조합 금지.**

## 리포트 형식

발견 항목은 심각도(critical/high/medium/low)와 함께 `docs/security-review-<날짜>.md`에 기록:
- **위치** (파일:라인) / **유형** (IDOR, RLS 누락 등) / **재현 시나리오** (어떤 요청으로 뚫리는지 구체적으로) / **수정 제안**
- 재현 시나리오를 못 쓰는 항목은 심각도를 낮추고 "추정"으로 표기 — 오탐으로 개발을 막지 않는다.
