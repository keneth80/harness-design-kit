# {{PROJECT_NAME}}

## 프로젝트 개요
- 도메인: {{DOMAIN}}
- 생성일: {{DATE}}

## CONTEXT.md

프로젝트의 도메인 용어 사전은 `CONTEXT.md`에 정의한다.
새로운 도메인 용어가 등장하면 반드시 CONTEXT.md에 추가할 것.
의사결정 기록은 `docs/adr/`에 ADR(Architecture Decision Record)로 남긴다.

## 코딩 규칙

### 공통
- TDD: vertical slice 단위. 테스트 1개 → 구현 → 테스트 1개 → 구현 반복. 테스트를 전부 먼저 쓰는 horizontal slicing 금지
- 테스트는 행위(behavior)를 검증. 내부 구현이 아닌 public interface를 통해 테스트
- 시크릿: 환경변수 또는 .env — 하드코딩 절대 금지
- 에러 핸들링: 구체적 예외 타입 사용, bare except 금지
- 커밋: conventional commits (feat:, fix:, refactor:, test:, docs:)
- 코딩 전에 grill(질문 공세)로 요구사항 정렬 먼저. `/grill` 커맨드 활용

### 설계 원칙
- 모듈은 깊게 만든다 — 간단한 인터페이스 뒤에 많은 기능을 숨긴다
- 불필요한 복잡성을 추가하지 않는다
- 변경은 최소 범위로 — 요청한 것만 수정한다 (Surgical Changes)

## Back-pressure (자기 검증)

작업 완료 시 Stop Hook이 자동으로 타입체크/린트/테스트를 실행한다.
실패하면 exit 2를 반환하여 에이전트가 에러를 수정할 때까지 재작업한다.
성공하면 완전히 침묵한다 (컨텍스트에 아무것도 추가하지 않음).

## 디렉토리 구조

- `src/` — 소스 코드
- `tests/` — 테스트
- `docs/adr/` — Architecture Decision Records
- `CONTEXT.md` — 도메인 용어 사전
- `.claude/` — 하네스 (skills, hooks, commands, rules)

상세 구조는 `Glob`으로 탐색할 것.
