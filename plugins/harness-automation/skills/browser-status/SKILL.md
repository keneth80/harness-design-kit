---
name: browser-status
description: CDP 디버깅 포트로 떠 있는 Chrome 인스턴스들의 연결 상태와 열린 탭 수를 점검하고, 문제가 있으면 원인과 해결책을 제시한다.
when_to_use: 크롬 연결 확인, CDP 안 붙어, 브라우저 상태, 9222 포트, connect_over_cdp 실패.
argument-hint: "[포트 ...]"
---

# 브라우저 상태 점검

점검할 포트: 인자(`$ARGUMENTS`)가 있으면 그 포트들, 없으면 `harness.config.json`의 `automation.cdp_ports`, 그것도 없으면 9222.

각 포트마다:
1. `curl -s --max-time 3 http://localhost:<포트>/json/version` → Browser 버전과 webSocketDebuggerUrl 확인
2. `curl -s --max-time 3 http://localhost:<포트>/json/list` → 열린 탭 수
3. 응답이 없으면 `lsof -i :<포트>`로 포트 점유 프로세스 확인

결과를 포트별 한 줄 표로 보여주고, 실패한 포트에는 원인 후보를 붙인다.
- Chrome이 `--remote-debugging-port` 없이 떠 있음 → 해당 프로필로 다시 실행
- 같은 `--user-data-dir`를 다른 Chrome이 쓰는 중 → 프로필 분리
- 다른 프로세스가 포트 점유 → 포트 변경

프로젝트에 로컬 LLM 서버 같은 의존 서비스가 있으면 CLAUDE.md에 적힌 상태 점검 명령도 함께 돌린다.
