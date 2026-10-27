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
