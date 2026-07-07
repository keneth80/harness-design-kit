---
name: tdd
description: 기능을 TDD(RED→GREEN→리팩토링) 사이클로 구현한다.
---

# TDD

이 기능을 TDD로 구현해줘.

1. 구현할 행위(behavior)를 하나 선택
2. RED: 그 행위에 대한 테스트 작성 → 실행 → 실패 확인
3. GREEN: 테스트를 통과시키는 최소 코드 작성
4. REFACTOR: 코드 정리 (테스트 통과 상태 유지)
5. 다음 행위로 반복

규칙:
- 한 번에 테스트 1개만 RED
- 행위를 테스트하지 구현을 테스트하지 않는다
- RED 상태에서 리팩토링하지 않는다
- horizontal slicing 금지 (테스트 전부 → 구현 전부)

`.claude/skills/tdd/SKILL.md` 참조.
