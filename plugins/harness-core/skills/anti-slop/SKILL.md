---
name: anti-slop
description: 화면 컴포넌트와 사용자에게 보이는 글에서 AI 기본값 티(보라 그라디언트, 장식 이모지, 줄표, 홍보성 형용사)를 빼는 기준과 slop 설정.
when_to_use: UI·문구·문서 작성, slop_scan 경고, AI가 쓴 것 같다.
argument-hint: "[검사할 파일 | 규칙 | 설정]"
allowed-tools: Bash(python3 *slop_scan.py*)
---

# AI 티 빼기

모델은 지시가 없으면 가장 흔한 답을 고른다. 그래서 어느 서비스에 붙여도 되는 화면과 글이 나온다. 기준은 하나다.
**이 주제가 아니면 나올 수 없는 선택인가?** 아니라면 기본값이다.

## 쓰기 전에

- 화면: 색·서체·간격은 디자인 시스템 토큰(`docs/design/`, `design-system` 스킬)에서 가져온다. 없으면 기존 코드의 값을 따른다.
- 글: 기능 이름 대신 사용자가 얻는 결과를, 형용사 대신 숫자·사례·동작을 쓴다. 실제 수치가 없으면 숫자를 지어내지 않는다.
- 프로젝트에 정한 말투(존댓말 수준, 용어 사전 `CONTEXT.md`)가 있으면 그걸 따른다.

## 피할 것과 대신 할 것

| 기본값 | 대신 |
|---|---|
| 보라→파랑 그라디언트, 그라디언트 글자 | 브랜드 색 하나와 중립색. 강조는 굵기·크기로 |
| 모든 카드가 `rounded-2xl shadow-lg` | 정보 위계에 따라 면, 선, 여백으로 구분 |
| 반투명 유리 카드 | 단색 면. 배경이 비쳐야 할 이유가 있을 때만 |
| 제목·목록 앞 이모지 | 빼거나 프로젝트 아이콘 세트 |
| Inter 단독 | 디자인 시스템에서 정한 서체 (한글은 한글 서체 지정) |
| "10K+ users", "99.9%" | 실제 수치, 없으면 빼기 |
| 지어낸 이용 후기, 가짜 고객 로고 | 실제 후기만. 없으면 섹션을 빼거나 비워 두고 사용자에게 알린다 |
| 줄표(—, ㅡ)로 문장 잇기 | 문장을 나누거나 쉼표·괄호 |
| 원활한, 혁신적인, 획기적인, 손쉽게, 극대화, 시너지 | 무엇이 얼마나 나아지는지 ("3초 안에 계산") |
| "~하는 것이 중요합니다" | 왜 중요한지, 안 하면 무엇이 깨지는지 |
| "단순히 ~가 아니라 ~" | 하는 일을 바로 말하기 |
| "~에 오신 것을 환영합니다", "고민하고 계신가요?" | 사용자가 얻는 것으로 시작 |
| "결론적으로," 머리말 | 결론만 |
| seamless, unlock, elevate, empower, delve | plain verbs and facts |

전체 규칙은 `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/slop_scan.py" --rules`로 본다.

## 훅이 알려줄 때

init한 프로젝트에서는 `slop_scan` 훅이 방금 추가한 줄만 검사한다 (기존 줄은 보지 않는다).
1. 걸린 줄을 위 표의 "대신"으로 고친다.
2. 의도한 것이면(브랜드 색이 실제로 보라색 등) 그대로 두고 이유를 한 줄로 말한다.
3. 계속 예외로 둘 표현이면 사용자에게 `slop.allow` 추가를 제안한다. 설정 파일은 직접 고치지 않는다.
4. 한 줄만 예외면 그 줄 주석에 `slop-ok`를 적는다.

정규식은 겉으로 드러나는 티만 잡는다. 걸린 게 없어도 "어디에나 붙일 수 있는 화면·글인가"는 직접 판단한다.
화면은 `/harness-design:design-review`의 8번(개성) 항목이 이 판단을 맡는다.

## 설정 (`harness.config.json`)

```json
"slop": {
  "mode": "warn",
  "judge": "stop",
  "ban": ["운명을 바꾸는", {"pattern": "100%\\s*적중", "message": "근거 없는 보장 표현", "id": "no-guarantee"}],
  "allow": ["ui-default-font"]
}
```

- `mode`: `warn`(기본, 쓴 뒤 알려줌) · `ask`(쓰기 전에 확인 창) · `off`
- `judge`: `stop`이면 응답을 끝낼 때 바뀐 화면·글 파일을 `slop-judge` 에이전트가 한 번 더 심사한다 (기본 `off`, `judge_rounds` 2, `judge_max_files` 8). 훅이 심사를 요청하면 Agent 도구로 `harness-core:slop-judge`를 부르고, 프롬프트에 파일 목록과 사용자가 직접 지정한 표현을 적는다
- `ban`: 프로젝트 금지 표현. 문자열은 그대로, `pattern`은 정규식. 서비스 고유의 과장·금지어를 여기에 둔다.
- `allow`: 규칙 id(`ui-glass`)나 표현(`강력한`). 걸린 부분에 이 표현이 있으면 넘어간다.
- `ui_paths`·`text_paths`·`ignore_paths`: 검사할 파일. 적으면 기본 목록을 대체한다. 글이 `.py`나 `content/**`에 있으면 `text_paths`에 더한다.
- 원장에 넣으려면 `"verify": {"slop": true}`. 커밋 기준(`slop.base`, 기본 HEAD)에서 바뀐 줄에 AI 티가 있으면 실패다.

## 직접 검사

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/slop_scan.py"                  # 커밋 이후 바뀐 줄과 새 파일
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/slop_scan.py" --base main      # 브랜치 전체 변경
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/slop_scan.py" --files src/Hero.tsx
```
