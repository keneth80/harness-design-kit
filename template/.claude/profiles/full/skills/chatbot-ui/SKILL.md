---
name: chatbot-ui
trigger: "챗봇|채팅|메시지|UI|컴포넌트|WebSocket|채팅창|입력창|버블"
---

# Chatbot UI Skill

Next.js 15 + React 19 기반 실시간 챗봇 인터페이스 구현 지식.

## 컴포넌트 설계 패턴

### ChatWindow
- 가상 스크롤 (메시지 1000+ 대비, @tanstack/virtual)
- 새 메시지 시 자동 스크롤 (사용자가 위로 스크롤 중이면 비활성)
- Optimistic UI: 전송 즉시 표시, 서버 응답으로 업데이트

### MessageBubble
- role별 스타일 분리: user(우측), assistant(좌측), system(중앙)
- 마크다운 렌더링 (react-markdown)
- 코드 블록 구문 강조
- 스크린샷 인라인 표시 (base64 → Image)
- 타임스탬프 hover로 표시

### InputBar
- Shift+Enter: 줄바꿈, Enter: 전송
- 텍스트 자동 높이 조절 (textarea, max 5줄)
- 전송 중 disabled + 로딩 스피너
- 음성 입력 버튼 (Web Speech API, 선택)

## WebSocket 연결 관리

```typescript
// hooks/useWebSocket.ts 패턴
function useWebSocket(url: string, userId: string) {
  // 1. 연결 시 userId로 인증
  // 2. 자동 재연결 (exponential backoff, 최대 5회)
  // 3. heartbeat ping/pong (30초 간격)
  // 4. 연결 상태 표시 (connected/reconnecting/disconnected)
  // 5. 메시지 큐 (연결 끊김 중 보낸 메시지 재전송)
}
```

## 가족 멀티유저 UI

- Header에 현재 사용자 아바타 + 이름 표시
- UserSwitch 컴포넌트: 가족 구성원 목록 → 클릭으로 전환
- 유저별 대화 히스토리 분리
- 유저별 테마/설정 (localStorage)

## 실시간 작업 상태 표시

```
[메시지 전송] → [의도 파악 중...] → [Google Sheets 검색 중...] 
  → [Meta Business Suite 접속 중...] → [메시지 발송 완료 ✅]
```

각 단계를 TaskProgress 컴포넌트에 스텝 인디케이터로 표시.
스크린샷이 오면 BrowserPreview에 실시간 업데이트.

## 다크/라이트 모드

```css
/* Tailwind CSS variables 패턴 */
:root {
  --chat-bg: theme(colors.white);
  --bubble-user: theme(colors.blue.500);
  --bubble-assistant: theme(colors.gray.100);
}
.dark {
  --chat-bg: theme(colors.gray.900);
  --bubble-user: theme(colors.blue.600);
  --bubble-assistant: theme(colors.gray.800);
}
```
