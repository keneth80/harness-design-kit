---
name: lessons
description: docs/lessons-learned.md(학습된 교훈)와 docs/error-log.md(오류 기록)를 요약해 보여주고, 교훈 등록·취소 요청을 error-curator에게 넘긴다.
when_to_use: 교훈 보여줘, 지난 오류 기록, 같은 실수 반복, 이건 교훈이야, L3 취소.
argument-hint: "[L번호 | E번호 | 자세히 | 취소]"
---

# 학습 기록 조회

1. `docs/lessons-learned.md`의 모든 L 엔트리를 요약한다: L번호, 제목, 위반 카운트, 관련 파일·외부 시스템, 재발 방지 규칙 한 줄.
2. `docs/error-log.md`의 최근 E 엔트리 10개를 요약한다: E번호, 사용자 보고 한 줄, 해결 여부, 승격 상태.
3. 통계: 전체 L 수, 전체 E 수, 최근 30일 신규 L, 위반 카운트 상위 3개.

인자(`$ARGUMENTS`) 처리
- `L3 자세히`, `E5 자세히` → 해당 엔트리 전문
- `L3 취소`, `이건 교훈이야: ...` → `harness-core:error-curator` 에이전트에 위임 (학습 기록은 error-curator만 고친다)

파일이 없으면 `/harness-core:init`으로 만들 수 있다고 안내한다.
