---
name: browser-automation
description: Playwright·CDP로 이미 떠 있는 Chrome에 붙어 자동화할 때의 초기화 순서, 멀티 인스턴스 구성, 세션 만료·다운로드·다이얼로그 처리 패턴.
when_to_use: 브라우저 자동화, CDP, connect_over_cdp, Playwright, Chrome 인스턴스, 다운로드, 권한, 프로필.
---

# Browser Automation Skill

Playwright CDP 연결 기반 멀티 Chrome 인스턴스 브라우저 자동화 지식.

## CDP 초기화 5단계 (필수)

매 연결 시 반드시 순서대로 실행:

```python
async def initialize_cdp(context: BrowserContext, download_path: str):
    """CDP 초기화 — 이 함수를 connect 직후 반드시 호출"""
    cdp = await context.new_cdp_session(context.pages[0])

    # 1. 다운로드 허용
    await cdp.send("Browser.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": str(Path(download_path).resolve())
    })

    # 2. 권한 설정
    for permission in ["clipboardReadWrite", "notifications", "geolocation"]:
        await cdp.send("Browser.setPermission", {
            "permission": {"name": permission},
            "setting": "granted"
        })

    # 3. 다이얼로그 자동 처리
    context.pages[0].on("dialog", lambda d: d.accept())

    # 4. 파일 선택기 캡처
    context.pages[0].on("filechooser", lambda fc: None)

    # 5. 새 탭 캡처
    context.on("page", lambda p: p.wait_for_load_state())
```

## Chrome 실행 플래그

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=~/chrome-profiles/google \
  --disable-popup-blocking \
  --disable-notifications \
  --disable-infobars \
  --noerrdialogs \
  --no-first-run
```

⚠️ Chrome 136+: `--remote-debugging-port`에 `--user-data-dir` 반드시 동반

## Playwright CDP 연결 패턴

```python
# ✅ 올바른 방법 — 기존 Chrome에 붙기
browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
context = browser.contexts[0]  # 기존 컨텍스트 재사용

# ❌ 사용하지 말 것 — 프로필 잠금 충돌
# browser = await playwright.chromium.launch_persistent_context(...)
```

## 에러 복구 패턴

| 에러 | 복구 전략 |
|------|----------|
| CDP 연결 끊김 | 3초 대기 → 재연결 (최대 3회, exponential backoff) |
| 세션 만료 | 사용자에게 "재로그인 필요" 알림 (프로젝트의 알림 채널) |
| 메모리 초과 | 불필요 탭 전체 닫기 → GC → 재시도 |
| 페이지 로드 타임아웃 | 30초 타임아웃 → 새 탭으로 재시도 |
| 요소 미발견 | 3초 대기 → 페이지 새로고침 → 재시도 |

## 서비스를 자동화하기 전에

- 공식 API가 있으면 브라우저 자동화보다 API를 먼저 쓴다 (예: Google Sheets는 Sheets API·gspread가 훨씬 안정적).
- 서비스 약관이 자동화를 허용하는지 확인한다. 탐지를 피하려는 장치는 만들지 않는다.
- 로그인 세션·쿠키가 담긴 프로필 폴더(`chrome-profiles/`)는 커밋하지 않는다 (.gitignore).
- 비밀번호는 코드나 설정 파일에 두지 않는다. 처음 한 번은 사람이 직접 로그인하고 세션을 재사용한다.
- 서비스별 셀렉터·URL 패턴은 프로젝트의 `.claude/skills/`에 따로 둔다 (예시: 저장소의 `examples/jarvis-chatbot`).

# 브라우저 자동화 코드를 작성할 때

## 작업 시작 전 필수 절차

### 절차 A: 학습된 교훈 검토

`docs/lessons-learned.md`에서 다음을 우선 확인하고 의무 준수:
- 외부 시스템이 "Browser", "Playwright", "Chrome", "CDP", "DOM"인 L 엔트리
- 관련 파일이 `browser_*.py`, `automation_*.py`, `*_browser.py`인 L 엔트리
- 위 모두 의무 준수, 위반해야 하면 사용자에게 먼저 확인

### 절차 B: 최근 오류 확인

`docs/error-log.md` 최근 5개 엔트리에서 브라우저 관련 오류가 있는지 확인.

### 절차 C: 명세 문서 참조 (풀 사이클 모드)

`docs/spec.md`에서:
- 자동화할 사이트 URL, 로그인 필요 여부
- 추출/입력해야 하는 데이터 구조
- 트리거 조건 (수동/스케줄/이벤트)
- 실패 시 동작 정책

## 다른 에이전트와의 명확한 경계

이 경계를 어기면 작업이 충돌합니다:

| 영역 | 담당 | 이 스킬이 다루지 않는 것 |
|---|---|---|
| 브라우저 안의 모든 조작 | **이 스킬** | — |
| HTTP API 엔드포인트 (FastAPI 등) | backend-dev | 절대 작성 안 함 |
| 외부 REST API 클라이언트 | integration 스킬 | ElevenLabs API 등은 만지지 않음 |
| 워크플로우 오케스트레이션 (LangGraph, state machine) | pipeline 스킬 | 단계별 흐름 관리는 안 함 |
| DB 쿼리, 스키마 | backend-dev | DB 코드 안 만짐 |
| UI 컴포넌트 | frontend-dev | — |

**이 스킬의 영역은 "브라우저 인스턴스를 받아서 조작하는 함수"까지**입니다.
이 함수를 호출하는 워크플로우, 결과를 저장하는 DB, 외부에 알리는 API는 다른 에이전트의 일입니다.

## 핵심 코딩 원칙

### DOM 변화에 강한 셀렉터

```python
# ❌ 절대 금지 — 절대 위치 셀렉터
page.click("body > div > div > div:nth-child(3) > button")

# ✅ 권장 — 의미 있는 셀렉터
page.click('[data-test-id="submit"]')
page.click('button[aria-label="Send message"]')
page.get_by_role("button", name="Submit").click()
```

### 대기 전략

```python
# ❌ 절대 금지 — DOM 준비 보장 안 됨
time.sleep(3)

# ✅ 권장 — 명시적 대기
page.wait_for_selector('[data-loaded="true"]')
page.wait_for_load_state("networkidle")
page.wait_for_function("() => document.querySelector('.result').innerText.length > 0")
```

### 스트리밍 응답 처리 (Gemini, ChatGPT 등)

```python
# 완료 시그널 대기 (Regenerate 버튼 출현 등)
page.wait_for_selector('[data-test-id="regenerate"]', timeout=120000)

# 또는 텍스트 길이 안정화 감지
async def wait_for_streaming_complete(page, selector, stable_seconds=2):
    last_length = 0
    stable_count = 0
    while stable_count < stable_seconds:
        await asyncio.sleep(1)
        text = await page.text_content(selector)
        current_length = len(text)
        if current_length == last_length:
            stable_count += 1
        else:
            stable_count = 0
            last_length = current_length
```

### 세션과 인증

```python
# 로그인 세션은 영구 프로필로 분리
context = await browser.new_context(
    storage_state="./profiles/main_session.json"
)

# 작업 후 저장
await context.storage_state(path="./profiles/main_session.json")
```

- 인증 실패 시 자동 재시도 절대 금지
- 사용자에게 즉시 알림 (텔레그램 봇 등)

### 에러 복구 정책

```python
async def robust_click(page, selector, max_retries=3):
    """재시도 가능한 클릭. 무한 재시도 금지."""
    for attempt in range(max_retries):
        try:
            await page.wait_for_selector(selector, timeout=5000)
            await page.click(selector)
            return True
        except TimeoutError:
            if attempt == max_retries - 1:
                raise BrowserAutomationError(
                    f"Selector not found after {max_retries} attempts: {selector}"
                )
            await asyncio.sleep(2 ** attempt)  # 지수 백오프
```

- 셀렉터 못 찾으면: 재시도 3회 → 사용자 알림
- 페이지 크래시: 새 컨텍스트로 재시작 (기존 컨텍스트 destroy)
- **절대 금지**: 무한 재시도, 조용한 실패(예외 삼키기), `except: pass`

### 헤드리스 vs 헤드풀 분기

```python
# 환경변수 또는 config로 분기
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

# 디버깅 시 HEADLESS=false
# 프로덕션 시 HEADLESS=true
```

### 결과 추출

```python
# ❌ 즉시 추출 — 렌더링 완료 보장 없음
text = page.text_content(".result")

# ✅ snapshot으로 안정성 확보
await page.wait_for_load_state("networkidle")
snapshot = await page.accessibility.snapshot()
text = await page.text_content(".result")
```

추출 직전 한 번 더 안정성 확인:
- `wait_for_load_state("networkidle")` 또는
- 특정 완료 시그널 대기

## 코드 작성 후 절차

1. **자가 점검**:
   - lessons-learned.md의 어떤 L 엔트리를 적용했는지 명시
   - 셀렉터가 의미 기반인지 (data-*, aria-label, role)
   - 모든 대기가 명시적인지 (`time.sleep` 없는지)
   - 에러 복구 경로가 모두 종착지가 있는지 (사용자 알림 또는 명시적 실패)

2. **검증 요청**:
   - 메인 세션에 "code-verifier로 검증 요청"이라고 명시

## 절대 어기지 말 것

- 백엔드 API 엔드포인트 코드 작성 금지 (backend-dev 영역)
- 외부 REST API 클라이언트 작성 금지 (integration 스킬 영역)  
- 워크플로우/state machine 작성 금지 (pipeline 스킬 영역)
- DB 코드 작성 금지 (backend-dev 영역)
- `time.sleep()` 사용 금지 (대기는 항상 명시적)
- 절대 위치 셀렉터 사용 금지
- 무한 재시도 또는 조용한 실패 금지
- lessons-learned.md의 재발 방지 규칙 위반 금지
- error-log.md, lessons-learned.md 직접 수정 금지

## 자주 사용되는 라이브러리

- **Playwright**: 브라우저 제어 표준
- **Browser Use**: AI 기반 브라우저 자동화 (선생님 OpenClaw 환경)
- **CDP (Chrome DevTools Protocol)**: 저수준 제어 필요 시
- **playwright-stealth**: 봇 탐지 회피 (필요 시)
