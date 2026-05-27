# Opus 설계 → Codex 구현 워크플로우

이 하네스는 **설계는 Claude(Opus), 구현은 Codex CLI**로 나누는 분업을 지원합니다.
두 에이전트는 직접 연결되지 않습니다. 디스크의 파일(매뉴얼 → AGENTS.override.md)이
인수인계 문서 역할을 하므로, 대화 맥락을 공유할 필요가 없습니다.

## 전체 흐름

1. **설계 (Claude Code / Opus)**
   - `domain-interview` 스킬로 도메인을 발견하고 인터뷰 → `interview.json`
   - `domain-manual` 스킬로 매뉴얼 생성 → `manual.md`, 도메인 지도 `README.md`
   - 인터뷰가 `complete`되면 `domain-manual`의 export 절로 매뉴얼을
     `AGENTS.override.md`로 내보내 각 도메인의 `code_paths`에 배치

2. **구현 (Codex CLI)**
   - 해당 코드 디렉터리에서 Codex 실행
   - Codex는 작업 디렉터리로 내려오며 `AGENTS.override.md`를 자동으로 읽고,
     거기 적힌 불변 규칙·의존 계약·핵심 모델을 지키며 구현
   - Codex는 이 하네스(.claude/, 스킬, 훅)를 읽지 못함 — AGENTS.override.md가 유일한 계약

3. **검증 (다시 Claude Code / Opus)**
   - Codex가 짠 코드를 Claude Code 세션에서 열면 `drift_guard` 훅이
     코드↔매뉴얼 어긋남을 감시
   - `domain-refactor` 스킬(report 모드)로 "Codex 코드 vs 매뉴얼" 위반을 진단

## 왜 양방향 실시간 차단이 아닌가 (정직한 한계)

Codex CLI에도 PreToolUse 훅이 있지만, **현재 apply_patch(파일 편집)에는
훅이 안정적으로 발동하지 않습니다**(shell 호출에는 발동). 따라서 drift_guard 같은
"미완성 도메인 코드 수정 차단"을 Codex 쪽에서 실시간으로 강제할 수 없습니다.

그래서 방어선은 이렇게 구성됩니다:
- **Codex 쪽 (예방):** AGENTS.override.md가 규칙을 명시 → Codex가 자율 준수
- **Opus 쪽 (검출):** drift_guard 훅 + domain-refactor가 사후에 위반을 잡음

Codex 훅이 apply_patch까지 커버하도록 개선되면, 그때 drift_guard.py를
Codex의 `.codex/hooks/`로 이식해 실시간 차단을 추가할 수 있습니다(현재는 보류).

## AGENTS.override.md 배치 규칙

- 위치: 매뉴얼 메타블록의 `code_paths` 디렉터리 (glob `**` 제거).
  예) `code_paths: src/domains/recommendation/**` → `src/domains/recommendation/AGENTS.override.md`
- Codex는 프로젝트 루트에서 작업 디렉터리까지 내려오며 각 단계에서
  AGENTS.override.md를 확인하고, **작업 위치에 가까운 것이 우선** 적용됨.
  따라서 코드 트리에 두면 그 코드를 만질 때 정확히 그 도메인 규칙이 적용됨.
- `interview_status: complete`가 아닌 도메인은 export하지 않음(미확정 규칙 굳음 방지).

## 주의
- AGENTS.override.md는 매뉴얼의 파생물이다. 직접 수정 금지.
  규칙을 바꾸려면 인터뷰 → 매뉴얼 → 재export 순서를 거친다.
- 매뉴얼이 갱신되면 AGENTS.override.md도 다시 export해야 동기화가 유지된다.
  (drift_guard가 매뉴얼↔코드는 감시하지만, 매뉴얼↔AGENTS.override.md 동기화는 수동)
