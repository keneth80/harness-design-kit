---
name: error-recovery
trigger: "에러|실패|안됨|연결 끊김|타임아웃|crash|ECONNREFUSED|Cannot connect|build failed"
---

# Error Recovery Skill

프로젝트 특화 에러 패턴과 복구 전략 모음.

## Frontend 에러

| 에러 | 진단 | 복구 |
|------|------|------|
| TypeScript 컴파일 에러 | `npx tsc --noEmit 2>&1` | 타입 수정, missing import 추가 |
| Next.js 빌드 실패 | `npm run build 2>&1` | 서버/클라이언트 컴포넌트 분리, "use client" 추가 |
| Hydration mismatch | 브라우저 콘솔 로그 | suppressHydrationWarning 또는 동적 import |
| WebSocket 연결 실패 | 네트워크 탭 확인 | URL 확인, CORS, FastAPI 서버 상태 |

## Backend 에러

| 에러 | 진단 | 복구 |
|------|------|------|
| FastAPI 시작 실패 | `python -m backend.app.main 2>&1` | import 순서, 의존성 누락 |
| CDP 연결 거부 | `curl localhost:9222/json/version` | Chrome 실행 여부, 포트 충돌 |
| CDP 세션 만료 | Playwright 에러 로그 | 재연결 + Telegram 알림 |
| LangGraph 라우팅 실패 | StateGraph 실행 로그 | 노드 연결, 상태 타입 확인 |

## 인프라 에러

| 에러 | 진단 | 복구 |
|------|------|------|
| Supabase 연결 실패 | `docker ps`, DB URL 확인 | docker compose up, .env 확인 |
| LM Studio 응답 없음 | `curl localhost:1234/v1/models` | 서버 시작, 모델 로드 확인 |
| Chrome 메모리 초과 | `ps aux | grep Chrome` | 불필요 탭 닫기, 인스턴스 재시작 |
| 포트 충돌 | `lsof -i :PORT` | 프로세스 종료 또는 포트 변경 |

## 자주 발생하는 에러 빠른 복구

**Cannot connect to CDP**
```bash
curl -s http://localhost:9222/json/version  # 진단
./backend/scripts/launch-chrome.sh stop && ./backend/scripts/launch-chrome.sh start  # 복구
```

**WebSocket connection failed**
```bash
curl -s http://localhost:8000/docs  # FastAPI 확인
# .env의 NEXT_PUBLIC_WS_URL과 FastAPI CORS 설정 점검
```

**LM Studio timeout**
```bash
curl -s http://localhost:1234/v1/models  # 서버 확인
# 검증 Hook은 graceful fallback으로 정적 분석만 동작 (에러 아님)
```
