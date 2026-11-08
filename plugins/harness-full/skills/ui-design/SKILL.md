---
name: ui-design
description: spec.md의 화면 목록을 바탕으로 mockup.md와 ui-spec.md를 만들고, 디자인 토큰을 지켜 화면을 구현한다. UI가 있는 프로젝트에서만 쓴다.
when_to_use: UI 설계, 화면 설계, 와이어프레임, 목업, ui-spec, 화면 스타일링, 다크모드, 반응형.
disable-model-invocation: true
---

# UI 설계

## 시작 전
1. `docs/spec.md`가 없으면 `/harness-full:plan-start`부터 하라고 안내한다.
2. spec.md의 "화면 목록"이 비었거나 도메인이 API·CLI면 "UI가 없는 프로젝트"라고 알리고 `/harness-full:test-cases`로 안내한다.
3. `docs/mockup.md`(화면별 와이어프레임)와 `docs/ui-spec.md`(컴포넌트 트리, 상태, 토큰)를 쓰고 사용자 검토를 받는다. 승인되면 `/harness-full:test-cases`로 넘어간다.

## 화면을 만들 때
비주얼 디자인 및 디자인 시스템 전문. 기획된 화면을 시각적으로 구현한다.

## 담당 영역
- `src/styles/` — 글로벌 스타일, CSS 변수, 디자인 토큰
- `src/components/` — 컴포넌트 스타일링 (Tailwind)
- `tailwind.config.ts` — 테마 확장
- `docs/design/` — 디자인 가이드

## 원칙
- 디자인 토큰 우선 — 하드코딩 컬러/사이즈 금지, CSS 변수 사용
- Tailwind utility-first — 커스텀 CSS 최소화
- 다크/라이트 모드 필수 — 모든 컴포넌트가 양쪽 모드에서 동작
- 모바일 우선 반응형 — `sm:`, `md:`, `lg:` 브레이크포인트
- 접근성 — 명도 대비 4.5:1 이상, 포커스 인디케이터, aria 속성

디자인 토큰, 컬러 팔레트, 타이포그래피, 컴포넌트 스타일 가이드는
프로젝트에 `design-system` 스킬(프로젝트 `.claude/skills/`)이 있으면 그 토큰을 따르고, 없으면 기존 코드의 토큰을 찾아 일관되게 쓴다.

## 디자인 품질 (harness-design이 켜져 있을 때 특히)
- 작업 전에 `docs/design/brief.md`를 읽는다. 없으면 `/harness-design:design-brief`를 먼저 제안한다.
- frontend-design 스킬이 있으면 그 원칙을 따른다: 주제에서 나온 선택, 템플릿 같지 않은 조합, AI 기본값(보라 그라디언트, 숫자 카드 3개, 이모지 아이콘) 피하기.
- 값은 토큰에서만 가져온다. design_guard 경고가 나오면 토큰으로 바꾼다.
- 상호작용하는 요소는 상태 6종(hover, active, focus, loading, empty, error)을 갖춘다. 문구는 자리표시가 아니라 실제 문장으로 쓴다. harness-design이 켜져 있으면 `/harness-design:design-review`의 마감 기준(finish.md)을 따른다.
- 화면 하나를 끝내면 `/harness-design:design-review`로 찍어서 확인하고 보고한다. 보지 않고 "완료"라고 하지 않는다.

## 작업 순서
1. 디자인 토큰 정의 (`src/styles/tokens.css`)
2. tailwind.config.ts 테마 확장
3. 글로벌 스타일 (`src/app/globals.css`)
4. 기본 레이아웃 → 챗 컴포넌트 → 상태 컴포넌트 순서
5. 다크모드 + 모바일 반응형 검증

