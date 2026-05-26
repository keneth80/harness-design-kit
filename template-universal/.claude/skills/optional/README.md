# Optional Skills

이 디렉토리의 스킬들은 **도메인에 따라 선택적으로 활성화**됩니다.
범용 하네스 본체에는 포함되지 않으며, 특정 기술 스택을 쓰는 프로젝트에서만 꺼내 씁니다.

활성화하려면 해당 스킬 폴더를 `.claude/skills/` 본체로 복사(또는 이동)하세요.
scaffold.sh가 도메인 입력에 따라 자동 추천하는 것이 이상적입니다(agents/optional 관례와 동일).

## 도메인별 추천 매핑

| 도메인 | 추천 스킬 | 짝이 되는 optional 에이전트 |
|---|---|---|
| `automation` | **browser-automation** | browser-dev, automation-dev |
| `agent` (멀티에이전트/JARVIS류) | **task-routing** | integration-dev, automation-dev |
| `youtube` / `video` | browser-automation | browser-dev, integration-dev |
| `general` / `webapp` / `api` | (없음 — 본체 스킬만) | — |

## 각 스킬

### browser-automation
Playwright CDP 연결 기반 멀티 Chrome 인스턴스 자동화 지식.
**언제 활성화**: 웹사이트 자동 조작 비중이 큰 프로젝트 (브라우저 에이전트, 자동 업로드, 모니터링).

### task-routing
LangGraph StateGraph 기반 의도 파악 및 서비스 라우팅 지식.
**언제 활성화**: 여러 서비스/에이전트로 요청을 분기하는 멀티에이전트 시스템.

## 주의
이 스킬들은 본체에 있지 않으므로 평소엔 트리거되지 않습니다.
프로젝트에서 쓰려면 본체로 옮긴 뒤, 트리거 충돌이 없는지 확인하세요
(특히 task-routing의 "그래프/파이프라인" 키워드).
