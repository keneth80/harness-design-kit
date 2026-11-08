# Changelog

차단·확인 규칙이나 훅이 내는 판정이 바뀐 항목은 **동작 변경**으로 따로 적습니다. 업데이트 전에 이 부분만 보면 됩니다.

## 2.8.0 — 2026-11-09

벤치마크 역제안. [REA와 e2e](https://www.peters.place/ko/post/rea-and-e2e)의 "완성품에서 거꾸로 분석해 내 서비스에 녹인다"는 생각을 웹사이트 벤치마킹에 맞게 가져왔습니다.

### 추가
- `/harness-full:benchmark <URL> [알고 싶은 것]`: 둘러보기 → 사이트별 분석 → 가져올 것·다르게 할 것·안 할 것 역제안 → 시나리오 초안
- `bench_crawl.mjs`: 공개 페이지만, robots.txt(그룹 선택, 가장 긴 규칙, Crawl-delay) 준수, 요청 간격, 정직한 User-Agent, 상태를 바꾸는 주소 건너뛰기, 폼은 구조만(입력값 안 읽음), API 호출 패턴(id 정규화), 스크린샷 자동 gitignore, `--check`
- `benchmark-analyst` 작업자(sonnet)와 `benchmark-playbook` 교본: 기능마다 확인됨·추정·모름 판정과 근거
- plan-start가 벤치마크 URL이 있으면 `/harness-full:benchmark`를 먼저 제안하고 기존 보고서를 반영
- 테스트 4개 (로컬 사이트로 robots·건너뛰기·입력값 비노출·API 패턴·페이지 한도, robots 규칙 해석)

## 2.7.0 — 2026-11-09

에이전트보다 스킬. 노하우는 전부 스킬에 두고, 에이전트는 독립 채점·병렬 작업자·세션 모드에만 남겼습니다 (16개 → 9개).

### 동작 변경
- **작업자 에이전트를 얇은 껍데기로**: architect, qa-tester, qa-engineer, backend-dev, frontend-dev의 절차를 숨은 작업 교본 스킬(`*-playbook`, `user-invocable: false`)로 옮기고, 에이전트는 `skills:`로 미리 불러옵니다. 워크플로우가 부르는 에이전트 이름은 그대로입니다
- **`/harness-full:architect`, `test-cases`, `qa-boundary`는 `context: fork`**로 해당 작업자에게 따로 떨어져 돌고 결과만 돌려줍니다
- **기획과 화면 설계는 메인 대화로**: ui-planner → `plan-start`(opus), ui-designer → `ui-design`. 질문을 사용자에게 바로 합니다
- **에이전트 삭제와 흡수**: error-curator → `lessons`("또 안 되네"로도 켜짐), error-handler → `error-recovery`(특정 스택 표를 일반 진단표로), browser-dev → `browser-automation`, integration-dev → `integration`, automation-dev → `pipeline`

### 추가
- `/harness-core:help`: 하고 싶은 일이나 프로젝트 상태를 보고 명령 1~3개 추천, 꺼진 플러그인은 켜는 방법까지
- [docs/GUIDE.md](docs/GUIDE.md): 처음 쓰는 사람을 위한 사용 가이드 (5분 시작, 개념 세 가지, 상황별 명령, 자주 쓰는 흐름, 막힐 때)
- 구조 테스트: 작업자 에이전트는 숨은 교본 하나를 불러오는 25줄 미만 껍데기, fork 스킬은 있는 에이전트를 가리킴, 가이드와 help의 명령이 모두 실제로 있음

## 2.6.0 — 2026-11-08

### 동작 변경
- **grill을 "가정 확인"으로**: 질문 공세 대신 이해한 목표·할 일·가정(근거 또는 짐작 표시)을 먼저 보여주고, 잘못 짐작하면 되돌리기 비싼 것(데이터 삭제 방식, 돈·권한·개인정보 규칙, 외부 공개 범위, 완성 기준, 범위 경계)만 최대 3개 묻습니다. 기술 선택은 묻지 않고 제안합니다
- grill은 이제 `/harness-full:grill`로 직접 부를 때만 돕니다 (자동 호출 끔)

## 2.5.0 — 2026-11-06

완성품을 켜서 확인하는 시나리오 검사. 선후 관계와 위험·복구 기록은 [vibe](https://github.com/su-record/vibe)의 시나리오 방식에서 아이디어를 얻었습니다 (코드는 새로 작성).

### 동작 변경
- `harness.scenarios.json`이 보호 대상 설정 파일에 추가됨. 처음 만드는 것은 허용, 있는 파일을 고치면 ask

### 추가
- 시나리오 엔진(`_lib.run_scenarios`)과 `scenario_run.py`: command·http 검사, `needs` 순서와 blocked, `${변수}`(없으면 skipped), 태그 선택, `risk`(영향·복구 안내·복구 확인 검사, 복구는 실행하지 않음)
- `verify.scenarios`(true 또는 id·태그 목록)로 원장에 묶기: verify_run, backpressure, fix-until-green, `/goal`이 시나리오까지 통과해야 pass
- `/harness-core:scenarios` 스킬과 `templates/harness.scenarios.json`
- 검사 실행을 `_lib.run_check`로 통일 (verify_run, backpressure)
- 테스트 157개

## 2.4.0 — 2026-11-06

루프 엔지니어링의 바닥 다지기. 루프가 기대는 통과 판정과 시험지를 에이전트 손에서 뺐습니다.

### 동작 변경
- **시험지 보호** (init한 프로젝트): 테스트에 skip·only 추가, 단언·테스트 수 감소, 기존 테스트 삭제·셸 덮어쓰기, 동결 파일(`golden/**`, `__snapshots__/**`, `*.snap`) 수정이 ask가 됩니다. `loop.protect_tests: false`로 끔
- **원장 쓰기 deny**: `.harness/verify-ledger.json`과 서명 키 `~/.claude/harness-data/ledger.key`는 에이전트가 쓸 수 없고, 키는 읽을 수도 없습니다
- **fix-until-green**: 통과 판정을 verify_run.py 원장으로 하고, 통과라고 나오면 다른 에이전트가 `--status`로 다시 확인합니다
- **full-cycle**: code-verifier의 판단과 원장이 둘 다 pass여야 `allVerified`
- **backpressure**: 원장이 지금 코드 그대로 pass면 다시 돌리지 않고, 직접 돌린 결과를 원장에 남깁니다

### 추가
- `verify_run.py`: 검사를 직접 돌리고 HMAC 서명과 작업 트리 지문으로 원장을 남김. state: pass, partial-pass, fail, stale, tampered, missing, unconfigured. 하네스 산출물은 지문에서 제외, `loop.fingerprint_ignore`로 추가
- `/harness-core:goal`: `/goal`에 원장 조건과 반복 상한을 붙여 걸기 (ProposeGoal이 있으면 바로 제안)
- `loop_setup.py`: 검사 명령 감지, 정답 데이터·테스트 경로 후보를 이름 규칙으로 찾아 제안하고 확인 후 적용. `/harness-core:init`이 이 진단으로 루프 설정을 안내
- 기본 테스트 경로에 Java·Kotlin·C#·Ruby·Scala·PHP·Swift·Dart·Elixir 규칙, 기본 동결에 `*.golden`, `*.golden.*`, `*.approved.*`
- code-verifier와 verify 스킬이 원장 상태를 리포트 맨 위에 적고, pass가 아니면 통과로 보고하지 않음
- CLAUDE.md 하네스 구역에 "루프와 통과 판정" 규칙
- 테스트 147개

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
