---
name: tdd
trigger: "TDD|테스트|test|red-green|리팩터|vertical slice"
---

# TDD Skill

Vertical slice 단위 Red-Green-Refactor 루프.

## 핵심 원칙

테스트는 **행위(behavior)**를 검증한다. 내부 구현이 아니라 public interface를 통해.
리팩토링했는데 테스트가 깨지면 — 그 테스트는 구현을 테스트하고 있던 것이다.

## Vertical Slice (올바른 방법)

```
RED:   하나의 행위에 대한 테스트 작성 → 실패 확인
GREEN: 그 테스트를 통과시키는 최소한의 코드 작성
REFACTOR: 테스트가 통과하는 상태에서 코드 정리
→ 다음 행위로 반복
```

## Horizontal Slicing (하지 말 것)

```
❌ 테스트를 전부 먼저 작성 → 구현을 전부 나중에 작성
```

이렇게 하면:
- 데이터 구조와 함수 시그니처를 테스트하게 됨 (행위가 아님)
- 구현을 이해하기 전에 테스트 구조에 갇힘
- 행위가 바뀌어도 테스트가 통과하고, 안 바뀌어도 테스트가 실패함

## 좋은 테스트 vs 나쁜 테스트

**좋은 테스트:**
- public API를 통해 호출
- 테스트 이름이 스펙처럼 읽힘: "user can checkout with valid cart"
- 리팩토링해도 안 깨짐

**나쁜 테스트:**
- 내부 함수를 직접 호출
- mock이 구현 세부사항에 의존
- private 메서드를 테스트
- DB를 직접 쿼리해서 검증 (인터페이스 대신)

## 실행 규칙

1. RED 상태에서 리팩토링하지 않는다. 먼저 GREEN으로 만들어라
2. 한 번에 하나의 테스트만. 여러 테스트를 동시에 RED로 두지 않는다
3. 각 사이클 후 `backpressure.py`가 자동으로 테스트 실행하여 검증
