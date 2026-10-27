---
name: dev-start
description: 세션을 시작할 때 프로젝트 현재 상태(git, 진행 중인 도메인, 검증 상태, TODO)를 파악하고 우선순위별 다음 작업 3가지를 제안한다.
when_to_use: 어디까지 했지, 이어서 작업, 오늘 뭐 하지, 현재 상태, 다음 작업 추천.
---

# 개발 시작

1. `git status`, `git log --oneline -8`로 최근 변경과 커밋되지 않은 작업을 확인한다.
2. 코드맵(세션 시작 때 주입됨, 없으면 `docs/codemap.md`)으로 구조를 잡는다. 전체 파일을 다 읽지 않는다.
3. `docs/domains/*/interview.json`의 status와 `open_questions`(blocks_completion)를 확인해 막힌 도메인을 찾는다.
4. `_workspace/`(harness-full 사용 시)의 최신 보고서와 `docs/verification-report.md`가 있으면 남은 실패를 확인한다.
5. `TODO|FIXME`를 Grep해 미완성 지점을 모은다.
6. `CONTEXT.md`의 용어가 최근 코드와 맞는지 훑는다.
7. 우선순위별 다음 작업 3가지를 제안한다. 각각 "왜 지금인지"와 "어떤 스킬·에이전트로 할지"를 한 줄씩 붙인다.
