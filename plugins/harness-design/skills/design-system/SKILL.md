---
name: design-system
description: 디자인 브리프에서 색·타이포·간격·모양·움직임 토큰을 도출해 프로젝트 스택에 맞는 토큰 파일로 만들고, design_guard와 화면 점검이 쓰도록 harness.config.json에 등록한다.
when_to_use: 디자인 토큰 만들기, 디자인 시스템 셋업, 컬러 팔레트, 타이포 스케일, 다크 모드 기준, 하드코딩 색 정리.
disable-model-invocation: true
---

# 디자인 토큰 만들기

두 번째 이유는 기준이 없어서다. 값을 한 곳에 모으면 화면이 늘어나도 일관성이 유지되고, design_guard가 이탈을 잡을 수 있다.

## 절차

1. **입력**: `docs/design/brief.md`가 없으면 `/harness-design:design-brief`부터. 기존 토큰(CSS 변수, tailwind 설정, theme 파일)이 있으면 새로 만들지 말고 그걸 정리·보완한다.
2. **스택 확인**: Tailwind v4(`@theme` in CSS) / Tailwind v3(`tailwind.config.*`) / 일반 CSS / CSS-in-JS 중 무엇인지 본다.
3. **값 도출**: `references/tokens.template.css`의 구조를 따르되 값은 브리프에서 끌어낸다.
   - 색: 무드 키워드와 레퍼런스에서 기본 톤 1개 + 강조색 1개. 나머지는 역할로 파생. 텍스트·보조 텍스트가 배경 대비 4.5:1을 넘는지 계산해서 확인한다.
   - 타이포: 서체 1~2종, 비율 하나로 만든 크기 단계, 본문 행간 1.5 이상.
   - 간격: 4px 격자. 모양(반경·그림자)은 브리프 무드에 맞게 하나의 성격으로.
   - frontend-design 스킬이 있으면 그 원칙(주제에서 나온 선택, 템플릿 같지 않은 조합)을 따른다. 없으면 사용자에게 한 번만 권한다:
     `claude plugin install frontend-design@claude-plugins-official`
4. **파일 쓰기**: 스택에 맞는 위치에 쓴다 (예: `src/styles/tokens.css`, Tailwind v4면 `@theme`에 같은 이름으로 매핑, v3면 `theme.extend`가 CSS 변수를 참조).
   사람이 읽는 요약을 `docs/design/tokens.md`에 표로 남긴다 (역할, 라이트 값, 다크 값, 대비비).
5. **등록**: `harness.config.json`에 추가한다 (설정 파일 수정이라 확인 창이 뜬다).
   ```json
   "design": {
     "tokens": ["src/styles/tokens.css"],
     "guard": "warn",
     "pages": [{ "label": "home", "url": "http://localhost:3000/" }]
   }
   ```
   `pages`는 화면 점검(capture)이 찍을 주소다. 개발 서버 주소를 사용자에게 확인한다.
6. **기존 하드코딩 정리 제안**: `rg -n "#[0-9a-fA-F]{3,8}\b" src`로 하드코딩 색 수를 세서 보고하고, 정리 작업을 따로 할지 묻는다. 이 스킬에서 일괄 치환하지 않는다.
