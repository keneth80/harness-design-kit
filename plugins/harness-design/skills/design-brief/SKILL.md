---
name: design-brief
description: 화면을 만들거나 고치기 전에 목적·사용자·무드·레퍼런스·금지 사항을 짧게 인터뷰해 docs/design/brief.md로 고정한다. 이후 디자인 작업과 design-critic의 채점 기준이 된다.
when_to_use: 디자인 시작, 화면 새로 만들기, 리디자인, 랜딩 페이지, 브랜드 느낌 잡기, 디자인 방향.
argument-hint: "[화면 또는 기능 이름]"
---

# 디자인 브리프

AI가 만든 화면이 평범해지는 첫 번째 이유는 방향이 없어서다. 코드 전에 방향을 한 장으로 고정한다.

## 절차

1. **있는 것부터 읽는다**: 기존 `docs/design/brief.md`, `docs/spec.md`, `CONTEXT.md`, README, 랜딩 문구.
   이미 답이 나와 있는 질문은 묻지 않는다.
2. **한 번에 묶어서 묻는다** (최대 6개). 사용자가 모르면 근거를 붙인 제안을 만들어 고르게 한다.
   - 이 화면의 주요 과업 한 가지
   - 주 사용자와 쓰는 상황
   - 무드 키워드 3개와 피하고 싶은 인상 3개
   - 좋아하는 레퍼런스 (서비스, 사이트, 사진, 잡지 무엇이든)
   - 고정된 브랜드 요소
   - 하지 말았으면 하는 것
3. **`references/brief.template.md` 형식으로 `docs/design/brief.md`를 쓴다.** 인자(`$ARGUMENTS`)가 특정 화면이면
   그 화면 이름을 제목에 넣는다. 여러 화면이면 공통 브리프 하나에 화면별 과업만 추가한다.
4. **금지 사항에 AI 기본값을 넣는다**: 사용자가 원하지 않는 한 "보라·파랑 그라디언트, 숫자+작은 라벨 카드 나열, 이모지 아이콘, 모든 것을 가운데 정렬"을 금지 목록에 둔다.
5. **랜딩·마케팅 페이지면** `/harness-design:landing-page`의 사전 질문을 같은 묶음에 넣고 브리프의 "8. 랜딩 페이지" 절을 채운다. 아니면 그 절을 지운다.
6. frontend-design 스킬(Anthropic 공식 플러그인)이 없으면 설치를 한 번 권한다: `claude plugin install frontend-design@claude-plugins-official`.
7. 다음 단계를 안내한다: 토큰이 없으면 `/harness-design:design-system`, 있으면 바로 작업 후 `/harness-design:design-review`.

## 하지 말 것
- 브리프 없이 "일단 예쁘게" 만들기 시작하지 않는다.
- 사용자가 준 레퍼런스를 그대로 베끼지 않는다. "가져올 점"만 가져온다.
