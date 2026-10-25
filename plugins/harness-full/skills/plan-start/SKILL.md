---
name: plan-start
description: 풀 사이클의 첫 단계. docs/goal.md(한 줄 목표) 또는 docs/prd.md를 읽고 ui-planner 에이전트로 requirements.md와 spec.md(기능정의서)를 만든다.
when_to_use: 기획 시작, 새 프로젝트 기획, PRD로 스펙 만들기, 요구사항 문서화.
disable-model-invocation: true
---

# 기획 시작

1. 입력 문서를 우선순위대로 확인한다.
   - `docs/spec.md`가 이미 있으면: 갱신할지, 그대로 두고 다음 단계로 갈지 묻는다.
   - `docs/prd.md`가 있으면 **PRD 직접 진입**: ui-planner를 인터뷰 최소화 모드로 부르거나, 바로 `/harness-full:architect`로 갈지 선택지를 준다.
   - `docs/goal.md`가 있으면: ui-planner가 한 줄 목표를 인터뷰로 키운다.
   - 셋 다 없으면: "docs/goal.md에 한 줄 목표를 적거나 docs/prd.md를 넣어주세요"라고 안내하고 멈춘다.
2. `harness-full:ui-planner`에 위임해 `docs/requirements.md`, `docs/spec.md`를 쓴다. 에이전트의 질문은 사용자에게 그대로 전달하고 답을 다시 넘긴다.
3. 끝나면 다음 단계를 안내한다.
   - 멀티스택: `/harness-full:architect` (빌드 골격·공유 타입)
   - UI 있음: `/harness-full:ui-design`
   - UI 없음(CLI·API): `/harness-full:test-cases`
