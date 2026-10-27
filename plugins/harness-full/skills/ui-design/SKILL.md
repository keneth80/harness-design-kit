---
name: ui-design
description: spec.md의 화면 목록을 바탕으로 ui-designer 에이전트가 mockup.md와 ui-spec.md를 만든다. UI가 있는 프로젝트에서만 쓴다.
when_to_use: UI 설계, 화면 설계, 와이어프레임, 목업, ui-spec.
disable-model-invocation: true
---

# UI 설계

1. `docs/spec.md`가 없으면 `/harness-full:plan-start`부터 하라고 안내한다.
2. spec.md의 "화면 목록"이 비었거나 도메인이 API·CLI면 "UI가 없는 프로젝트"라고 알리고 `/harness-full:test-cases`로 안내한다.
3. `harness-full:ui-designer`에 위임해 `docs/mockup.md`, `docs/ui-spec.md`를 쓴다.
4. 사용자 검토를 받고, 승인되면 `/harness-full:test-cases`로 넘어간다.
