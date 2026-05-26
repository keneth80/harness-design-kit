# Optional Dev Agents

이 디렉토리의 에이전트들은 **도메인에 따라 선택적으로 활성화**됩니다.

scaffold.sh 실행 시 도메인 입력에 따라 자동으로 추천되며, 사용자가 수동 선택도 가능합니다.

## 도메인별 자동 추천 매핑

| 도메인 | 자동 추가되는 dev | 의도 |
|---|---|---|
| `general` | (없음 — 사용자 직접 선택) | 범용 |
| `webapp` | (기본만) frontend + backend | 일반 웹앱 |
| `api` | (기본만) backend | API 서버, frontend 제외 |
| `automation` | **browser-dev + automation-dev** | 브라우저 자동화 에이전트 |
| `video` | **integration-dev + automation-dev** | 영상 제작만 (업로드 별도) |
| `youtube` | **browser-dev + integration-dev + automation-dev** | 영상 제작 + 자동 업로드 |
| `agent` | **integration-dev + automation-dev** | 멀티 에이전트 시스템 (JARVIS 류) |
| `mobile` | (기본만) frontend + backend | 모바일 앱 |

## 각 dev 에이전트 역할

### browser-dev
브라우저 자동화 전담. Browser Use, Playwright, CDP, DOM 조작.
**언제 추가**: 웹사이트를 자동으로 조작하는 코드가 비중 큰 프로젝트
**예시 프로젝트**: 브라우저 에이전트, YouTube 자동 업로드 봇, 가격 모니터링

### integration-dev
외부 API 통합 전담. ElevenLabs, OpenAI, Google API 등의 클라이언트.
비용 안전장치, rate limit, 응답 검증.
**언제 추가**: 외부 SaaS API를 여러 개 사용하는 프로젝트 (특히 종량제)
**예시 프로젝트**: 영상 자동 제작, 멀티 LLM 에이전트, 챗봇

### automation-dev
워크플로우/state machine 전담. LangGraph, 체크포인트, 재시작 로직.
**언제 추가**: 다단계 파이프라인이 길게 도는 프로젝트
**예시 프로젝트**: 영상 제작 파이프라인, 브라우저 자동화 시퀀스, 에이전트 오케스트레이션

## 도메인 선택 가이드

### video vs youtube vs automation

영상 관련 프로젝트는 세 가지로 갈립니다:

- **`video`**: 영상 본편만 자동 제작. 업로드는 사람이 수동 (CapCut에서 마감 후)
- **`youtube`**: 본편 자동 + 유튜브 자동 업로드까지 (브라우저 자동화 추가)
- **`automation`**: 브라우저 작업이 주된 자동화. 영상 제작 비중 적음

### agent vs general

- **`agent`**: LangGraph 멀티 에이전트, 외부 LLM 다수 통합 (JARVIS, 챗봇)
- **`general`**: 위 카테고리에 안 맞는 일반 프로젝트

### api vs webapp vs mobile

- **`api`**: 순수 백엔드 서버 (frontend 코드 없음)
- **`webapp`**: 풀스택 웹 (Next.js + FastAPI 같은 구조)
- **`mobile`**: React Native, Flutter 같은 모바일 앱

## 명확한 역할 경계

여러 dev가 활성화될 때 누가 뭘 할지 헷갈리지 않도록:

```
backend-dev:    HTTP API 엔드포인트, 비즈 로직, DB
frontend-dev:   UI 컴포넌트, 화면, 클라이언트 측 상태
browser-dev:    브라우저 안에서 일어나는 모든 것 (DOM, 셀렉터, 추출)
integration-dev: 외부 서비스를 호출하는 클라이언트 코드
automation-dev:  비동기 장기 실행 + 상태 보존 + 재개
```

## 수동 추가/제거

```bash
# 추가
cp template/.claude/agents/optional/browser-dev.md \
   <project>/.claude/agents/

# 제거
rm <project>/.claude/agents/browser-dev.md
```

추가/제거 후 Claude Code 재시작.
