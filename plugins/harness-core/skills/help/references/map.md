# 상황별 명령 지도

플러그인 이름 뒤에 (core)·(full)·(design)·(codex)·(automation)을 붙였다. core 외에는 그 프로젝트에서 켜야 보인다.

## 처음 시작할 때
| 하고 싶은 일 | 명령 |
|---|---|
| 이 프로젝트에 하네스 켜기 (검사 명령·정답 데이터 설정 포함) | `/harness-core:init` (core) |
| 지금 상태와 다음 할 일 3개 | `/harness-core:dev-start` (core) |
| 뭘 써야 할지 모르겠다 | `/harness-core:help` (core) |

## 만들기 전에
| 하고 싶은 일 | 명령 |
|---|---|
| 큰 작업 전에 내가 원하는 걸 제대로 이해했는지 맞추기 | `/harness-full:grill` (full) |
| 한 줄 목표를 기획서(spec.md)로 | `/harness-full:plan-start` (full) |
| 잘되는 서비스를 둘러보고 가져올 기능을 제안받기 | `/harness-full:benchmark <URL>` (full) |
| 새 시스템이나 여러 영역이 얽힌 설계 | `/harness-core:domain-interview` → `/harness-core:domain-manual` (core) |
| 화면 방향 정하기 | `/harness-design:design-brief` → `/harness-design:design-system` (design) |
| 랜딩 페이지 구조와 문구 | `/harness-design:landing-page` (design) |

## 만들 때
| 하고 싶은 일 | 명령 |
|---|---|
| 기획서대로 처음부터 끝까지 자동으로 | `/harness-full:full-cycle` (full, 워크플로우) |
| 같은 흐름을 단계마다 확인하며 | `/harness-full:orchestrator` (full) |
| 빌드 골격과 공유 타입만 | `/harness-full:architect` (full) |
| 화면 설계와 구현 | `/harness-full:ui-design` (full) |
| 테스트부터 | `/harness-full:test-cases`, `/harness-full:tdd` (full) |
| 설계는 Claude, 구현은 Codex | `/harness-codex:codex-handoff` → `/harness-codex:codex-review` (codex) |
| 브라우저 자동화, 외부 API 연동, 장시간 파이프라인 | `browser-automation`, `integration`, `pipeline` 스킬 (automation, 관련 작업이면 자동으로 켜짐) |

## 확인할 때
| 하고 싶은 일 | 명령 |
|---|---|
| 지금 코드가 괜찮은지 (린트·테스트·스펙·교훈) | `/harness-core:verify` (core) |
| 통과할 때까지 알아서 고치기 | `/harness-full:fix-until-green` (full) 또는 `/harness-core:goal` (core) |
| 완성품을 켜서 확인, 배포 후 확인 | `/harness-core:scenarios` (core) |
| 바뀐 코드를 내가 이해하기 | `/harness-core:code-review` (core) |
| 보안 구멍 (권한, 다른 사람 데이터 접근) | `/harness-core:security-review` (core) |
| 백엔드와 프론트가 맞물리는지 | `/harness-full:qa-boundary` (full) |
| 정한 설계 규칙을 코드가 어겼는지 | `/harness-core:domain-refactor` (core), 전체는 `/harness-full:domain-sweep` (full) |
| 화면 품질 (스크린샷, 접근성, 채점) | `/harness-design:design-review` (design) |
| 시안 여러 개 겨루기 | `/harness-design:design-polish` (design, 워크플로우) |

## 문제가 생겼을 때
| 하고 싶은 일 | 명령 |
|---|---|
| 버그 원인 찾기 | `/harness-full:diagnose` (full) |
| 오류 메시지 해석과 복구 | `/harness-full:error-recovery` (full) |
| 같은 실수가 반복된다, 교훈으로 남기기 | `/harness-core:lessons` (core) |
| 하네스가 왜 막았지 | `/harness-core:audit` (core) |
| CLAUDE.md가 길어져서 규칙을 잘 안 지킨다 | `/harness-core:slim` (core) |
| 구조가 꼬였다, 개선점 | `/harness-full:architecture` (full) |
| 크롬 자동화 연결이 안 된다 | `/harness-automation:browser-status` (automation) |
