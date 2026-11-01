# Changelog

차단·확인 규칙이나 훅이 내는 판정이 바뀐 항목은 **동작 변경**으로 따로 적습니다. 업데이트 전에 이 부분만 보면 됩니다.

## 2.3.0 — 2026-11-01

설치 검토(2026-11-01)에서 나온 개선점 중 동작에 관한 것을 반영했습니다.

### 동작 변경
- **보안 게이트 오류 시 ask**: bash_gate·file_gate의 판정 로직이 예외를 내거나 공통 모듈(`_lib.py`)을 불러오지 못하면, 지금까지는 감사 로그에 `error`만 남기고 통과시켰습니다. 이제 사용자 확인(ask)으로 돌리고 화면에 한 줄 경고를 띄웁니다. 정상 판정의 출력은 그대로입니다.
- **design-polish 사전 점검**: 시작할 때 Node·Playwright·Chromium을 먼저 확인하고, 없으면 방향·목업·심사 에이전트를 띄우기 전에 멈춥니다.

### 추가
- 세션 시작 때 지난 알림 이후(최대 24시간)의 게이트 판정 오류 건수를 한 번 알림, python3가 3.9 미만이면 경고
- 동적 워크플로우가 환경변수로 꺼져 있으면 세션 시작 때 모델에 알려, 워크플로우 명령을 즉석에서 대신 수행하지 않고 사용자에게 안내하게 함. CLAUDE.md 하네스 구역에도 같은 규칙 (`/harness-core:init`을 다시 실행하면 반영)
- `capture.mjs --check`: 측정 도구 준비 점검 (준비 안 됐으면 exit 3과 설치 안내)
- design-review 첫 단계 준비 점검과 **축소 모드** (설치를 원하지 않으면 Browser pane이나 사용자 스크린샷으로 채점하고, 수치 측정 생략을 명시)
- GitHub Actions CI: Python 3.9·3.12 매트릭스 + Node, Playwright 측정은 별도 잡. `HARNESS_REQUIRE`로 도구가 없을 때 조용히 건너뛰지 않게 함
- 테스트 120개 (게이트 오류·모듈 로드 실패·세션 알림·사전 점검)

### 문서
- README: 요구 환경, deny와 ask가 보이는 모습(auto 모드·무인 실행·시크릿), 비용과 지연, 가볍게 시작하는 설정, Claude Code 내장 기능과의 관계, 문제 해결
- CHANGELOG에 **동작 변경** 구분을 둠

## 2.2.0 — 2026-10-28

[elayadesign/ai-design-skills](https://github.com/elayadesign/ai-design-skills)의 landing-page-design에서 하네스와 겹치지 않는 부분만 가져왔습니다.

- **landing-page 스킬** (harness-design): 사전 질문, 섹션 구조, 레이아웃 유형 A~D, 전환 원칙, 문구 틀, 작업 순서(`docs/design/landing-copy.md` 먼저), SEO/AEO. 랜딩·마케팅 페이지에서만 켜지고 시각 값은 정하지 않음
- **마감 기준 finish.md**: 콘텐츠 사실감과 금지 상투어(한국어 추가), 대시 금지, 상태 6종, 출시 전 목록, 겹친 반경·줄바꿈(`keep-all` 추가)·움직임 규칙, 한국어 서체 확인
- design-critic 기준표가 마감 기준과 랜딩 기준을 8개 항목의 감점으로 반영 (항목 수와 통과 기준은 그대로)
- capture.mjs에 출시 점검(`ship`, `summary.shipIssues`): lang, title, description, og:image, h1 하나, `<main>`, 본문 바로가기, `href="#"`, 한글 제목 `word-break`
- 디자인 브리프 템플릿에 "8. 랜딩 페이지" 절, design-system에 한국어 서체·겹친 반경·움직임 지침
- design-polish 목업과 ui-designer가 마감 기준을 따름
- 가져오지 않은 것: 고정 서체·색·간격 표, 히어로 텍스트 그라디언트, 필수 태그라인 섹션, "모든 UI에 적용" 트리거
- `plugins/harness-design/THIRD_PARTY_NOTICES.md`에 MIT 고지 (ai-design-skills, taste-skill)

## 2.1.0 — 2026-10-28

AI 오케스트레이션과 디자인 품질 기능을 넣었습니다.

- **harness-design 플러그인 추가**: design-brief, design-system(토큰 도출), design-review(4종 스크린샷 + 접근성 측정 + 채점 루프), design-critic 에이전트(opus, 읽기 전용), design_guard 훅(하드코딩 색·임의값 경고), capture.mjs
- **design-polish 워크플로우**: 시안 경쟁 → 블라인드 심사 3인 → 1위 다듬기 → 최종 재채점
- **harness-full 워크플로우**: full-cycle, fix-until-green, domain-sweep (동적 워크플로우, 이어서 실행 가능)
- **task_gate 훅**: 에이전트 팀 팀원의 작업 완료 전에 린트·타입체크
- **버그 수정**: ui-designer, error-handler 에이전트의 `tools:`가 비어 있던 문제
- ui-designer가 브리프·토큰·design-review를 따르도록 보강
- 테스트 106개 (워크플로우 흐름 테스트 포함)

## 2.0.0 — 2026-10-26

v1(템플릿 복사 방식)을 Claude Code 플러그인 마켓플레이스로 전면 재구성했습니다. 옮기는 방법과 바뀐 점은 [docs/MIGRATION.md](docs/MIGRATION.md).

- 플러그인 4종: harness-core(상시), harness-full, harness-codex, harness-automation(프로젝트별)
- 보안 게이트 재작성: bash_gate(토큰 단위 해석), file_gate(쓰기 전 시크릿·개인정보 차단, Read로 .env 열기 차단), 플러그인·설정 변조 방지
- verify_guard 결과가 모델 컨텍스트에 실제로 전달되도록 수정
- drift_guard: deny JSON, 경로 경계·메타 주석 버그 수정
- backpressure: 변경 없으면 생략, 3회 연속 실패 시 중단
- 스킬 frontmatter를 Claude Code 형식(description, when_to_use)으로, 모델 지정을 별칭으로
- claude-codex-harness를 harness-codex로 흡수, 매뉴얼 → AGENTS.override.md 내보내기를 스크립트화
- 감사 로그를 프로젝트 밖(플러그인 데이터 디렉터리)으로, /harness-core:audit
- 회귀 테스트 79개 (평범·주입·과잉 3변형)

## 1.x

템플릿 복사 + scaffold.sh + lite/full 프로파일. 마지막 커밋 57a6824.
