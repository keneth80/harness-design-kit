---
name: browser-automation
trigger: "브라우저|CDP|Chrome|playwright|자동화|다운로드|권한|크롬|인스턴스|프로필"
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
| 세션 만료 | Telegram "재로그인 필요" 알림 발송 |
| 메모리 초과 | 불필요 탭 전체 닫기 → GC → 재시도 |
| 페이지 로드 타임아웃 | 30초 타임아웃 → 새 탭으로 재시도 |
| 요소 미발견 | 3초 대기 → 페이지 새로고침 → 재시도 |

## 서비스별 참고 사항

### Google Sheets
- URL 패턴: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`
- 셀렉터: 시트 UI가 Canvas 기반 → 키보드 네비게이션 + Ctrl+F 검색 활용
- 대안: gspread API 사용 권장 (브라우저보다 안정적)

### Meta Business Suite
- URL 패턴: `https://business.facebook.com/latest/inbox`
- DM 답장: 대화 선택 → 입력창 포커스 → 메시지 입력 → Enter
- 주의: Meta 봇 탐지 위험 — 작업 간 랜덤 딜레이(2-5초) 필수
