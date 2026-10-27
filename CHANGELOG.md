# Changelog

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
