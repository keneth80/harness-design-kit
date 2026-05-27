---
name: pr-review
description: 현재 브랜치의 변경사항을 리뷰한다(코딩 규칙·범위·품질 점검).
---

# PR 리뷰

현재 브랜치의 변경사항을 리뷰해줘.

1. 현재 브랜치와 대상 브랜치 확인: `git branch --show-current`
2. main/develop과의 diff 확인: `git diff main...HEAD --stat`
3. 변경된 파일별로 아래 관점에서 리뷰:

## 리뷰 체크리스트

### 보안
- [ ] 하드코딩된 시크릿 없음
- [ ] SQL injection / XSS 위험 없음
- [ ] 인증/인가 누락 없음
- [ ] WebSocket 메시지에 민감 정보 없음

### 성능
- [ ] N+1 쿼리 패턴 없음
- [ ] 불필요한 리렌더링 없음
- [ ] CDP 연결/탭 미해제 없음
- [ ] 메모리 누수 가능성 없음

### 코드 품질
- [ ] TypeScript strict 모드 준수
- [ ] Python 타입 힌트 완비
- [ ] 에러 핸들링 적절
- [ ] 네이밍 컨벤션 일관성

### 프로젝트 규칙
- [ ] CDP 초기화 5단계 준수 (browser-automation 스킬)
- [ ] WebSocket 메시지 포맷 { type, payload, userId, timestamp } 준수
- [ ] .env 사용 (하드코딩 없음)

4. 이슈 발견 시 심각도(critical/high/medium/low)와 수정 제안 제시
5. 전체 요약 + PR 설명문 초안 생성
