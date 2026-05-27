---
name: diagnose
description: 버그를 재현→최소화→원인규명 순으로 체계적으로 진단한다. 추측 수정 금지.
---

# Diagnose

이 버그를 체계적으로 진단해줘.

1. REPRODUCE — 재현 가능한 최소 단계 확보
2. MINIMISE — 재현 케이스를 최소 크기로 축소
3. HYPOTHESISE — 원인 가설 (근거 기반, 추측 아님)
4. INSTRUMENT — 로그/assert로 가설 검증
5. FIX — 최소 범위 수정
6. REGRESSION TEST — 회귀 테스트 추가

추측으로 코드 수정하지 말 것. `.claude/skills/diagnose/SKILL.md` 참조.
