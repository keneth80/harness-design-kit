---
name: error-recovery
description: 자주 만나는 빌드·런타임·연결 오류의 진단 명령과 복구 전략 표. 에러 메시지를 보고 원인을 좁힐 때 쓴다.
when_to_use: 빌드 실패, 연결 거부, 타임아웃, ECONNREFUSED, 크래시, 원인 모를 에러.
---
# Error Recovery

자주 만나는 에러 패턴과 복구 전략. 프로젝트 고유 패턴은 `docs/lessons-learned.md`(error-curator가 관리)에 쌓인다.

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
| LangGraph 라우팅 실패 | StateGraph 실행 로그 | 노드 연결, 상태 타입 확인 |

## 인프라 에러

| 에러 | 진단 | 복구 |
|------|------|------|
| Supabase 연결 실패 | `docker ps`, DB URL 확인 | docker compose up, .env 확인 |
| Chrome 메모리 초과 | `ps aux | grep Chrome` | 불필요 탭 닫기, 인스턴스 재시작 |
| 포트 충돌 | `lsof -i :PORT` | 프로세스 종료 또는 포트 변경 |

## 자주 발생하는 에러 빠른 복구

**WebSocket connection failed**
```bash
curl -s http://localhost:8000/docs  # FastAPI 확인
# .env의 NEXT_PUBLIC_WS_URL과 FastAPI CORS 설정 점검
```
