---
name: codex-review
description: Codex가 구현한 코드를 도메인 매뉴얼과 대조해 위반을 찾고, 검증을 돌리고, 매뉴얼에 없는 결정을 드러낸다. Claude는 고치지 않고 리포트와 Codex용 수정 지시문만 만든다.
when_to_use: Codex 결과 검토, Codex가 짠 코드 확인, 구현 끝났어, 매뉴얼대로 됐는지.
argument-hint: "[도메인]"
---

# Codex 결과 검토

1. **변경 파악**: `git diff`/`git log`로 Codex가 바꾼 범위를 확인하고, 각 파일이 어느 도메인의 code_paths에 속하는지 매핑한다.
2. **매뉴얼 대조**: 해당 도메인마다 `domain-refactor` 스킬(report 모드)로 불변 규칙·의존 계약 위반을 찾는다.
3. **검증**: `/harness-core:verify`로 정적 분석·테스트를 돌린다 (code-verifier는 읽기 전용이라 설계 전용 모드와 충돌하지 않는다).
4. **결정 표면화**: 매뉴얼에 없는데 Codex가 정한 설계 결정(새 엔티티, 에러 정책, 의존 추가)을 목록으로 만든다.
   타당하면 인터뷰·매뉴얼에 반영하고 재export, 아니면 되돌리도록 지시문을 쓴다.
5. **리포트**: `docs/reviews/<YYYY-MM-DD>-codex-<도메인>.md`에 저장한다.
   - 위반 목록 (파일:라인, 어긴 규칙, 심각도)
   - Codex에게 줄 수정 지시문 (그대로 복사해 쓸 수 있게)
   - 매뉴얼 갱신 제안
