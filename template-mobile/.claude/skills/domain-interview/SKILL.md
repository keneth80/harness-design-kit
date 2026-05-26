---
name: domain-interview
trigger: "도메인 설계|도메인 인터뷰|새 시스템 설계|도메인 나누기|도메인 발견|모순 점검|설계 인터뷰|구현 전 확인"
---

# Domain Interview

구현 전에 도메인 요구사항을 빠짐없이 수집하고, 답변들 사이의 모순을 검출해 결정 기록으로 남기는 스킬.

**언제 쓰나:** 새 도메인/시스템을 설계하거나 여러 도메인이 얽힌 큰 건일 때. 막연한 의도에서 도메인 자체를 발견하고 경계를 긋는 Phase 0(discovery)부터 시작한다. 기존 시스템에 단일 기능만 얹는 가벼운 정렬이면 이 스킬이 아니라 grill을 쓴다. 결과는 docs/domains/_discovery/interview.json 및 docs/domains/<domain>/interview.json에 저장되며, 코드를 짜기 전에 이 인터뷰가 complete 되었는지 확인한다.

핵심 원칙: **이것은 설문이 아니라 모순 검출이다.** 자유롭게 많이 묻는 게 목적이 아니라, 필수 슬롯이 전부 채워지고 미해결 모순이 0이 될 때까지 묻는 **유한 루프**다.

## 2단계 구조

도메인은 미리 정해져 있지 않다. 인터뷰가 도메인 자체를 발견한다.

- **Phase 0 — 도메인 발견 (discovery):** 사용자의 막연한 의도에서 출발해 도메인 후보를 뽑고, 묶고, 경계를 긋는다. `_discovery`라는 메타 도메인으로 취급해 `docs/domains/_discovery/interview.json`에 기록한다. 일반 인터뷰와 **완전히 같은 Read→검증→Write 루프**를 쓴다.
- **Phase 1 — 도메인별 심층 인터뷰:** Phase 0에서 확정된 각 도메인에 대해 슬롯 채우기 + 모순 검출을 돈다. 도메인 유형은 Phase 0의 `domain_map.types`에서 자동으로 정해지므로 다시 묻지 않는다.

Phase 0가 `complete` 되기 전에는 어떤 도메인도 Phase 1로 넘어가지 않는다.

## 종료 조건 (반드시 충족)

`status: complete`는 다음 셋을 모두 만족할 때만 설정한다:
1. `required: true` 슬롯이 전부 `filled: true`
2. `open_questions` 중 `blocks_completion: true`가 0개
3. 미해결 모순 0개 (Phase 0에서는 도메인 경계 모순 포함)

하나라도 미충족이면 `in_progress`를 유지하고 인터뷰를 계속한다.

## 교착 처리 (무한 루프 방지)

같은 모순을 두고 (a)/(b)를 되물었는데도 사용자가 양립 불가능한 답을 반복하면, 무한히 되묻지 않는다. 대신:
- 같은 모순을 **2회 되물어도 안 풀리면**, 양쪽 선택지와 각각의 트레이드오프를 명확히 정리해 보여주고 "지금 정하기 어려우면 보류하고 진행할 수 있다"고 제안한다.
- 사용자가 보류를 택하면, 그 모순을 `open_questions[]`에 `blocks_completion: true`로 기록하고 다른 슬롯으로 넘어간다. 단 이 경우 인터뷰는 **complete가 될 수 없으며**, 종료 시 "이 항목이 정해지지 않아 구현을 시작할 수 없다"고 분명히 알린다.
- 사용자가 둘 다 원한다고 하면 그건 보통 도메인이 덜 나뉜 신호다 — 분리로 양립 가능한지 검토한다(예: k-tone에서 카탈로그 분리로 두 출처 문제를 푼 것처럼).

## 상태 파일

도메인별 상태는 `docs/domains/<domain>/interview.json`에 둔다. 이 파일이 단일 진실 공급원(single source of truth)이다. 컨텍스트가 압축되어도 매 턴 이 파일을 다시 읽어 전체 상태를 복원하므로, **답변 기록과 모순 검증은 항상 메모리가 아닌 이 파일을 근거로 한다.**

## 워크플로우

### Phase 0 — 도메인 발견 (최초, 도메인이 정해지지 않았을 때)
- `docs/domains/_discovery/` 폴더를 만들고 `interview-state.template.json`을 복사해 `interview.json`을 만든다. `preset: discovery`로 설정하고, 슬롯은 `references/slots.yaml`의 `discovery_slots`(intent / domain_map / boundaries)를 사용한다.
- 막연한 의도에서 시작한다: 무엇을 만들려는지(goal), 누가 쓰는지(actors), 범위(in/out_of_scope).
- **행위자는 반드시 한 번 더 캐묻는다.** 사용자가 처음 답한 행위자는 보통 "일반 사용자"에 그친다. 운영자/관리자/검수자/외부 시스템 등 데이터를 *생성·검증·승인*하는 숨은 행위자가 있는지 명시적으로 물어 actors를 닫는다. (숨은 행위자는 뒤 슬롯에서야 드러나면 경계를 다시 그어야 하므로 intent에서 잡는다.)
- 의도에 등장하는 명사·행위를 도메인 후보로 뽑고, 묶고(grouping), 각 도메인 유형(types)을 정한다.
- **경계를 점검한다.** `contradiction-patterns.md`의 "Phase 0 전용: 도메인 경계 모순"으로 책임 중복·공유 개념 불일치·순환 의존·과대/과소 분할을 검출한다. 발견 시 그 자리에서 (a)/(b)로 되묻는다.
- discovery 슬롯 3개가 채워지고 경계 모순이 0이 되면 `_discovery`의 `status`를 `complete`로 바꾼다. 확정된 도메인 목록과 경계를 사용자에게 보여주고 Phase 1 진입을 안내한다.

### Phase 1 시작 (도메인별, _discovery가 complete된 후)
- `_discovery`의 `domain_map`에 확정된 각 도메인마다 `docs/domains/<domain>/` 폴더와 `interview.json`을 만든다.
- 도메인 유형(types)에 맞는 프리셋을 `slots.yaml`에서 적용한다 (auth면 auth_flow를 required로 등). 유형은 이미 Phase 0에서 정해졌으므로 다시 묻지 않는다.

### 공통 턴 루프 (Phase 0·1 모두 동일)

#### 1. 매 턴 시작 — 상태 읽기
- `interview.json`을 **Read** 한다. 절대 기억에 의존하지 않는다.
- 채워지지 않은 required 슬롯과 미해결 open_questions를 파악한다.

#### 2. 질문 선택 — 한 번에 1~2개만
- Phase 0에서는 intent → domain_map → boundaries 순으로 묻는다.
- Phase 1에서는 모순 가능성이 높은 순서로 묻는다: **data_model → api_contract → external_deps → auth_flow → error_handling → edge_cases**.
- 이미 채워졌거나 이전 답변에서 추론 가능한 필드는 건너뛴다 (재질문 금지).
- 한 턴에 1~2개 필드만 묻는다. 수십 개를 한꺼번에 던지지 않는다.

#### 3. 답변 기록 + 모순 검증 (스킬의 본질)
답변을 받으면:
- 해당 슬롯 필드에 기록한다.
- **`references/contradiction-patterns.md`를 기준으로 기존 슬롯 전체와 교차 검증한다.** 3유형(직접 충돌 / 슬롯 간 암묵 모순 / 미명시 잠재 모순) 모두 점검. Phase 0에서는 "도메인 경계 모순"도 함께 점검.
- **직접 충돌·암묵 모순 발견 시 → 그 자리에서 즉시 (a)/(b) 양자택일로 되묻는다.** 나중에 몰아 묻지 않는다. 해소되면 `decisions[]`에 `resolved_conflict`와 함께 기록하고 `contradictions_resolved`를 +1.
- **잠재 모순(미명시) → `open_questions[]`에 추가**하고 `blocks_completion` 여부를 판단. 종료 전 반드시 해소.
- **소급 수정 허용.** 새 답이 이전에 채워진 슬롯의 가정을 깨면, 그 이전 슬롯을 거슬러 올라가 수정한다(예: 새 행위자 등장 → intent의 actors 갱신, 새 도메인 발견 → domain_map 갱신). 이전 슬롯은 한 번 채웠다고 동결되지 않는다. 수정 시 `decisions[]`에 무엇을 왜 바꿨는지 남긴다.

#### 4. 매 턴 끝 — 상태 쓰기 + 진행률
- 갱신된 상태를 `interview.json`에 **Write** 한다.
- 진행률을 한 줄로 보여준다: `[Phase N] 필수 슬롯 X개 중 Y개 완료 · 미해결 모순 K건 · open Q L건`. 사용자가 끝을 가늠하게 한다.

#### 5. 종료
- 종료 조건 3가지가 모두 충족되면 `status: complete`로 바꾸고, 확정된 결정 요약을 사용자에게 보여준다.
- Phase 0(`_discovery`)가 complete되면 → Phase 1로 넘어가 도메인별 폴더를 만든다.
- Phase 1의 각 도메인이 complete되면 → 그 `interview.json`이 다음 단계(도메인 매뉴얼 생성)의 입력이 된다고 안내한다.

## 참고 파일
- `references/slots.yaml` — 슬롯 정의와 도메인 프리셋. 시작 시 + 슬롯 구조가 헷갈릴 때 읽는다.
- `references/contradiction-patterns.md` — 모순 검출 체크리스트. **답변을 검증하는 매 턴 참조**.
- `references/interview-state.template.json` — 상태 파일 초기 템플릿. 인터뷰 시작 시 복사용.

## 하지 말 것
- 모순 검증 없이 다음 질문으로 넘어가지 말 것 (그러면 설문지에 불과함).
- 한 턴에 슬롯 전체를 쏟아내지 말 것.
- required 슬롯이 비었거나 모순이 남았는데 `complete`로 표시하지 말 것.
- 기억에 의존해 모순을 판단하지 말 것 — 항상 `interview.json`을 근거로.
- 이미 채운 슬롯을 동결하지 말 것 — 새 정보가 이전 가정을 깨면 거슬러 수정한다.
- 같은 모순을 3회 이상 되묻지 말 것 — 교착 처리로 넘어간다.
