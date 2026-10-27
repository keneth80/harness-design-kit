---
name: codex-handoff
description: complete된 도메인 매뉴얼을 Codex CLI가 읽는 AGENTS.override.md로 내보내 각 도메인의 code_paths에 둔다. 불변 규칙·의존 계약·핵심 모델과 공통 코딩 규칙이 Codex에게 전달되는 유일한 통로.
when_to_use: Codex에게 넘기기, 핸드오프, AGENTS.override.md 만들기, 매뉴얼 바뀐 뒤 재export.
argument-hint: "[도메인 ...]"
---

# Codex 핸드오프

Codex는 Claude 하네스(플러그인·스킬·훅)를 읽지 못한다. AGENTS.override.md가 스스로 완결된 작업 지시서여야 한다.
자세한 배경은 `references/codex-handoff-guide.md`.

## 절차

1. 미리보기:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/export_agents.py" --project "$PWD" --dry-run
   ```
   특정 도메인만이면 `--domain <이름>`을 붙인다 (인자: `$ARGUMENTS`).
2. `skipped`가 있으면 이유를 사용자에게 알린다.
   - 인터뷰가 complete가 아님 → `domain-interview`로 마무리
   - §7 미해결 항목 → 결정이 필요하다고 알리고 멈춘다 (미확정 규칙이 코드에 굳는 걸 막는다)
   - code_paths 없음 → `domain-manual`로 메타 블록을 채운다
3. 문제가 없으면 `--dry-run` 없이 실행해 파일을 쓴다.
4. 결과를 보고하고 Codex 실행 위치와 첫 지시문을 제안한다. 예:
   `cd src/domains/recommendation && codex "AGENTS.override.md의 규칙대로 추천 API를 TDD로 구현해줘"`

## 하지 말 것
- AGENTS.override.md를 손으로 고치지 않는다. 규칙 변경은 인터뷰 → 매뉴얼 → 재export.
- 매뉴얼 §5 근거·§6 함정·§7 미해결은 내보내지 않는다 (스크립트가 알아서 뺀다).
