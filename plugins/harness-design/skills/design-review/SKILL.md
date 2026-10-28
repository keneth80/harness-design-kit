---
name: design-review
description: 화면을 모바일·데스크톱 × 라이트·다크로 찍고 접근성·반응형을 기계로 잰 뒤, design-critic(opus)이 브리프와 기준표로 채점한다. 재작업이면 상위 3개를 고치고 다시 찍는 루프를 최대 3라운드 돈다.
when_to_use: 디자인 리뷰, 화면 점검, 이거 예뻐?, 디자인 다듬기, 출시 전 UI 점검, 다크 모드 확인, 모바일 깨짐 확인.
argument-hint: "[페이지 라벨 | URL] [--no-fix]"
---

# 디자인 리뷰 루프

세 번째 이유는 결과를 눈으로 보지 않아서다. 찍고, 보고, 고치고, 다시 찍는다.

## 0. 준비

- 브리프(`docs/design/brief.md`)가 없으면 먼저 만들지 사용자에게 묻는다. 없이 진행하면 일반 기준으로만 채점된다.
- 개발 서버가 떠 있어야 한다. `harness.config.json`의 `design.pages` 주소에 `curl -sI`로 확인하고, 안 떠 있으면 프로젝트의 dev 명령을 백그라운드로 띄운다.
- **데스크톱 앱의 Browser pane 도구가 있는 세션이면** 그 도구로 직접 열어 보고 스크린샷을 찍어도 된다. 그래도 아래 capture는 돌린다 (네 가지 조건과 수치 측정 때문에).

## 1. 찍고 재기

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/capture.mjs" --config harness.config.json --out docs/design/shots
```

특정 화면만이면 `--url <주소> --label <이름>` (인자: `$ARGUMENTS`). Playwright가 없다고 나오면 설치 명령을 사용자에게 보여주고 동의를 받는다.
출력의 `summary`를 먼저 본다: 로드 실패, 대비 문제, 모바일 넘침, 이름 없는 컨트롤 수, 출시 점검(`shipIssues`).

## 2. 채점

`harness-design:design-critic` 에이전트에게 맡긴다:
"docs/design/brief.md와 기준표로 docs/design/shots/의 스크린샷과 report.json을 평가해줘. 판정, 항목별 점수, 발견, 먼저 고칠 3가지."

## 3. 고치기 (판정이 재작업이고 `--no-fix`가 아닐 때)

- critic이 꼽은 **상위 3가지만** 고친다. 한 라운드에 다 고치려 하지 않는다.
- 값은 토큰으로 고친다. 토큰에 없는 값이 필요하면 토큰을 먼저 추가한다.
- harness-full이 켜져 있으면 `harness-full:ui-designer`에게 맡겨도 된다.
- 고친 뒤 1번부터 다시. **최대 3라운드.** 같은 지적이 두 라운드 연속 남으면 멈추고 사용자에게 판단을 넘긴다 (브리프와 충돌할 가능성이 높다).

## 4. 기록

`docs/design/reviews/<YYYY-MM-DD>-<라벨>.md`에 라운드별 점수 변화, 남은 발견, 대표 스크린샷 경로를 남긴다.
사용자에게는 점수 변화(예: 평균 3.1 → 4.2)와 남은 major 이상 발견만 짧게 보고한다.
