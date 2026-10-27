# 예시: 프로젝트 전용 자산 (JARVIS 브라우저 챗봇)

v1의 `template/`(JARVIS 챗봇 특화 템플릿)에서 **그 프로젝트에만 해당하는 것**을 떼어 둔 예시입니다.

v2의 원칙은 단순합니다.
- 어느 프로젝트에서나 쓰는 것 → 플러그인 (harness-core, harness-automation 등)
- 이 프로젝트에서만 의미 있는 것 → 그 프로젝트 저장소의 `.claude/`

| 파일 | 내용 | 쓰는 법 |
|---|---|---|
| `.claude/skills/chatbot-ui/` | 챗봇 화면 컴포넌트·WebSocket 연동 규칙 | 프로젝트 `.claude/skills/`로 복사 |
| `.claude/skills/design-system/` | 디자인 토큰·다크모드·반응형 | 복사 후 토큰을 프로젝트 값으로 수정 |
| `.claude/rules/cdp-init.md` | CDP 연결 직후 초기화 5단계 | `.claude/rules/`로 복사 |
| `.claude/rules/ws-protocol.md` | WebSocket 메시지 포맷 | `.claude/rules/`로 복사 |
| `.claude/commands/browser-status.md` | 고정 포트(9222~9224) + LM Studio 점검 | 범용 버전은 `/harness-automation:browser-status` |

```bash
# JARVIS 저장소 루트에서
cp -R <이 저장소>/examples/jarvis-chatbot/.claude/. .claude/
```

harness-automation 플러그인과 함께 쓰면 browser-dev·automation-dev 에이전트가 이 규칙을 읽고 작업합니다.
