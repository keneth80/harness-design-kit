---
name: help
description: 하네스로 지금 하려는 일에 맞는 명령을 1~3개 골라 준다. 프로젝트 상태(초기화 여부, 기획서, 디자인 브리프, 검사 결과)를 보고 다음 한 걸음을 제안하고, 필요한 플러그인이 꺼져 있으면 켜는 방법을 알려준다.
when_to_use: 하네스 뭐 써야 해, 어떤 명령, 사용법, 도움말, 처음인데, 뭐부터, 이럴 땐 뭐 써.
argument-hint: "[하고 싶은 일]"
allowed-tools: Read, Glob, Bash(ls:*)
---

# 하네스 길잡이

## 1. 상황을 본다 (조용히, 빠르게)

```bash
ls harness.config.json docs/spec.md docs/prd.md docs/goal.md docs/design/brief.md harness.scenarios.json .harness/verify-ledger.json 2>/dev/null
```

- `.harness/verify-ledger.json`이 있으면 Read로 `passed`와 `created`만 본다 (마지막 검사가 통과였는지, 언제였는지).

- 사용할 수 있는 스킬 목록에서 `harness-full:`, `harness-design:`, `harness-codex:`, `harness-automation:`이 보이는지로 켜진 플러그인을 판단한다.

## 2. 고른다

`${CLAUDE_PLUGIN_ROOT}/skills/help/references/map.md`의 표에서 하고 싶은 일(`$ARGUMENTS`)에 맞는 명령을 1~3개 고른다.
인자가 없으면 상황으로 고른다:
- `harness.config.json`이 없다 → `/harness-core:init`
- 기획서가 없는데 새로 만드는 중 → `/harness-full:grill` 또는 `/harness-full:plan-start`
- 원장 상태가 fail이나 stale → `/harness-core:verify` 또는 `/harness-full:fix-until-green`
- 화면 작업인데 브리프가 없다 → `/harness-design:design-brief`
- 그 밖 → `/harness-core:dev-start`

## 3. 답한다

짧게, 쉬운 말로. 형식:

```
지금 상황: <한 줄>
추천: /명령 — 무엇을 해 주는지 한 줄 (왜 지금 이게 맞는지)
다음에: /명령 — 한 줄
```

- 추천한 명령의 플러그인이 꺼져 있으면 켜는 명령을 같이 준다: `claude plugin enable <플러그인>@harness-design-kit --scope local`
- 표 전체를 보여주지 않는다. 사용자가 "전부 보여줘"라고 하면 그때 map.md를 요약해 보여준다.
- 명령을 대신 실행하지 않는다. 사용자가 고르게 한다.
