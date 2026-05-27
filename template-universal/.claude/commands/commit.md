---
name: commit
description: 변경사항을 분석해 conventional commit 메시지를 생성한다.
---

# 커밋

변경사항을 분석해서 conventional commit을 생성해줘.

1. `git status`와 `git diff --staged`로 변경 내용 파악
2. 스테이징 안 된 파일이 있으면 관련 파일만 `git add` 할지 물어봐
3. 변경 내용을 분석해서 conventional commit 메시지 생성:
   - `feat:` 새 기능
   - `fix:` 버그 수정
   - `refactor:` 리팩토링
   - `test:` 테스트
   - `docs:` 문서
   - `style:` 포맷팅
   - `chore:` 기타
4. 커밋 메시지를 보여주고 확인 후 `git commit` 실행
5. 여러 성격의 변경이 섞여있으면 분리 커밋을 제안

예시 출력:
```
feat: WebSocket 실시간 메시지 스트리밍 구현

- useWebSocket 훅 추가 (자동 재연결, heartbeat)
- ChatWindow에 실시간 메시지 렌더링
- FastAPI WebSocket 엔드포인트 연결
```
