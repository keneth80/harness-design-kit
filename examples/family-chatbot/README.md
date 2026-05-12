# Family Chatbot — 도메인 특화 예제

이 디렉토리는 jarvis-harness-kit의 **가족 챗봇 도메인** 잔재를 보존한 예제입니다.

## 들어 있는 것

```
.claude/
├── commands/
│   └── browser-status.md            — /browser-status (Chrome 인스턴스 + LM Studio 상태)
├── rules/
│   ├── cdp-init.md                   — Chrome DevTools Protocol 초기화 5단계
│   └── ws-protocol.md                — WebSocket 메시지 포맷 표준
└── skills/
    ├── browser-automation/SKILL.md   — Playwright + CDP 멀티 인스턴스
    ├── chatbot-ui/SKILL.md           — Next.js 챗봇 화면 패턴
    └── task-routing/SKILL.md         — LangGraph StateGraph 라우터
```

## 사용 방법

가족 챗봇류 프로젝트(WebSocket 기반 실시간 챗 + 브라우저 자동화)를 만든다면:

```bash
# 1. 일반 풀 사이클 프로젝트 생성
bash scaffold.sh my-chatbot webapp

# 2. 이 예제의 commands/rules/skills를 복사
cp -r examples/family-chatbot/.claude/commands/* my-chatbot/.claude/commands/
cp -r examples/family-chatbot/.claude/rules/*    my-chatbot/.claude/rules/
cp -r examples/family-chatbot/.claude/skills/*   my-chatbot/.claude/skills/

# 3. CLAUDE.md의 하네스 트리거에 키워드 추가
# 예: "챗봇, 브라우저 자동화, WebSocket 관련 작업 시 이 스킬을 사용하라"
```

## 왜 본 템플릿에서 분리했나

이 룰과 스킬은 가족 챗봇 도메인(`JARVIS Browser Chatbot`)에 특화되어 있어 일반 프로젝트에 자동 주입되면 노이즈가 됩니다. 예제로 분리해서:

- 새 프로젝트는 자기 도메인의 스킬만 갖게 함 (오케스트레이터 트리거 충돌 방지)
- 같은 도메인 프로젝트는 여기서 복사해서 빠르게 부트스트랩
- 다른 도메인 예제(`examples/{도메인}/`)를 추가할 수 있는 패턴 확립

향후 `scaffold.sh --preset=family-chatbot`로 자동 주입할 수 있도록 확장 예정.
