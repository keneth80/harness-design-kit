---
name: design-system
trigger: "디자인 토큰|컬러|팔레트|타이포|다크모드|반응형|브레이크포인트|MessageBubble|InputBar|TaskProgress"
---

# Design System Skill

JARVIS 챗봇 UI 디자인 시스템 정의.

## 컬러 토큰

```css
:root {
  --color-primary-50: #eff6ff;
  --color-primary-500: #3b82f6;
  --color-primary-900: #1e3a5f;
  --color-success: #22c55e;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --color-bg-primary: #ffffff;
  --color-bg-secondary: #f8fafc;
  --color-bg-chat: #f1f5f9;
  --color-text-primary: #0f172a;
  --color-text-secondary: #64748b;
  --color-text-muted: #94a3b8;
}

.dark {
  --color-bg-primary: #0f172a;
  --color-bg-secondary: #1e293b;
  --color-bg-chat: #1e293b;
  --color-text-primary: #f1f5f9;
  --color-text-secondary: #94a3b8;
  --color-text-muted: #64748b;
}
```

## 타이포그래피

```
H1: 24px/700/-0.02em  H2: 20px/600  H3: 16px/600
Body: 14px/400/1.6    Caption: 12px/400   Code: 13px/monospace
```

## 간격: 4 → 8 → 12 → 16 → 24 → 32px

## 컴포넌트 스타일

**MessageBubble**
- User: `bg-primary-500 text-white rounded-2xl rounded-br-md`
- Assistant: `bg-bg-chat text-primary rounded-2xl rounded-bl-md`
- System: `bg-transparent text-muted text-center text-sm`

**InputBar**
- Container: `sticky bottom-0 bg-bg-primary border-t px-4 py-3`
- Textarea: `bg-bg-secondary rounded-xl resize-none max-h-32`
- Button: `bg-primary-500 rounded-full w-10 h-10 disabled:opacity-50`

**TaskProgress**
- Active: `bg-primary-500 animate-pulse`
- Complete: `bg-success` + checkmark
- Pending: `bg-bg-secondary border-dashed`

## 반응형

```
Mobile  (< 640px):  사이드바 숨김, 풀스크린 채팅
Tablet  (640-1024): 사이드바 오버레이
Desktop (> 1024):   사이드바 + 채팅 나란히
```
