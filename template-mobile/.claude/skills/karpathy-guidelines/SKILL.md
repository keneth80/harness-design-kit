---
name: karpathy-guidelines
description: LLM 코딩 4대 함정(과도한 추측, 과도한 복잡성, 무관한 수정, 약한 성공 기준)을 줄이는 행동 지침. 코드를 작성·수정·리뷰·리팩토링하기 직전에 자동 호출되어 dev/code-verifier 에이전트의 작업 품질을 끌어올린다. Andrej Karpathy의 LLM 코딩 관찰에서 도출.
trigger: "코드 작성|구현|리팩토링|수정|리뷰|review|implement|refactor"
license: MIT (multica-ai/andrej-karpathy-skills)
---

# Karpathy Guidelines — LLM 코딩 4원칙

LLM이 코드 작성 시 빈번히 저지르는 4가지 실패 패턴에 대한 대응 지침입니다. 단순 작업(오타 수정 등)에는 판단으로 건너뛰어도 됩니다. **비자명한 작업에서는 비용이 큰 실수를 줄이기 위해 caution > speed로 기울입니다.**

근거: Andrej Karpathy의 LLM 코딩 관찰
> "The models make wrong assumptions on your behalf and just run along with them. They don't manage their confusion, don't seek clarifications, don't surface inconsistencies, don't present tradeoffs, don't push back when they should."

---

## 1. Think Before Coding — 추측하지 말고, 혼란을 숨기지 말고, 트레이드오프를 드러내라

구현 직전에:

- **가정을 명시한다** — 불확실하면 묻는다.
- **여러 해석이 가능하면 모두 제시한다** — 침묵하며 하나를 골라 진행 금지.
- **더 간단한 접근이 있으면 말한다** — 정당하면 push back.
- **혼란스러우면 멈춘다** — 무엇이 불분명한지 짚고 묻는다.

신호: "이 사용자는 X를 원할 가능성이 70%, Y가 30%다" 같은 분기가 보이면 즉시 사용자 확인.

## 2. Simplicity First — 문제를 푸는 최소한의 코드, 추측성 기능 금지

과도한 엔지니어링과 싸운다:

- 요청하지 않은 기능 추가 금지.
- 단일 사용처 코드에 추상화 만들기 금지.
- 요청하지 않은 "유연성"이나 "확장성" 추가 금지.
- 일어날 수 없는 시나리오에 에러 처리 추가 금지.
- 200줄을 50줄로 줄일 수 있으면 다시 쓴다.

**자가 검증 질문**: "시니어 엔지니어가 이 코드를 보고 '과하다'고 할 것 같은가?" 그렇다면 단순화.

## 3. Surgical Changes — 필요한 곳만 손대고, 자기 흔적만 청소하라

기존 코드 수정 시:

- 인접한 코드/주석/포매팅을 "개선"하지 않는다.
- 고장 나지 않은 것을 리팩토링하지 않는다.
- 기존 스타일을 따른다 — 본인 취향과 다르더라도.
- 관련 없는 죽은 코드를 발견하면 **언급만 하고 삭제는 하지 않는다**.

변경이 만들어낸 고아 처리:

- **본인 변경이 만든** 미사용 import/변수/함수만 정리한다.
- 기존부터 죽어있던 코드는 요청 없이 지우지 않는다.

**자가 검증 질문**: 변경한 모든 라인이 사용자 요청까지 직선으로 추적되는가?

## 4. Goal-Driven Execution — 성공 기준을 정의하고, 검증될 때까지 반복하라

명령형 요청을 검증 가능한 목표로 변환:

| 약한 (명령형) | 강한 (목표 + 검증) |
|---|---|
| "검증 추가해줘" | "잘못된 입력에 대한 테스트 작성 → 통과하게 구현" |
| "버그 고쳐줘" | "버그 재현 테스트 작성 → 통과하게 수정" |
| "X 리팩토링해줘" | "리팩토링 전후 동일 테스트가 통과해야 함" |

다단계 작업에는 짧은 계획과 단계별 검증 체크포인트를 함께 제시:

```
1. [단계] → 검증: [체크]
2. [단계] → 검증: [체크]
3. [단계] → 검증: [체크]
```

강한 성공 기준이 있으면 LLM이 사용자 도움 없이 독립적으로 반복할 수 있습니다.

---

## 이 스킬이 작동하는 신호

- diff에 불필요한 변경이 줄어듭니다 (요청한 변경만 보입니다)
- 과도한 복잡성으로 다시 쓰는 일이 줄어듭니다 (처음부터 간단합니다)
- 명확화 질문이 **구현 전**에 옵니다 (실수 후가 아니라)
- PR이 깔끔하고 최소합니다 (drive-by refactor 없음)

## 본 하네스의 다른 에이전트들과의 연결

- **backend-dev / frontend-dev**: 구현 직전에 이 4원칙 자가 점검.
- **code-verifier**: Layer C/D 검증 시 "이 코드가 4원칙을 어겼는가?"를 별도 항목으로 봅니다.
- **architect**: 빌드 골격 만들 때 *Surgical Changes* 가장 중요 — 비즈니스 로직 침범 금지.
- **qa-tester**: *Goal-Driven Execution*을 명시적으로 구현 — 모든 테스트는 측정 가능한 기준만.

## 원본

multica-ai/andrej-karpathy-skills (MIT License)
https://github.com/multica-ai/andrej-karpathy-skills
