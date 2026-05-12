# CDP 초기화 규칙

BrowserManager.connect() 호출 후 반드시 CDP 초기화 5단계를 실행해야 합니다.
초기화 없이 페이지 조작을 시작하면 다운로드 실패, 권한 거부, 다이얼로그 미처리 버그가 발생합니다.

초기화 순서:
1. Browser.setDownloadBehavior
2. Browser.setPermission (clipboardReadWrite, notifications, geolocation)
3. page.on("dialog") 핸들러
4. page.on("filechooser") 핸들러
5. context.on("page") 새 탭 캡처

상세 코드는 `.claude/skills/browser-automation/SKILL.md` 참조.
