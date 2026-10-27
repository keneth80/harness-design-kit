<!--
  도메인 매뉴얼 템플릿 (docs/domains/<domain>/manual.md)

  이 파일은 고정 섹션 구조다. 섹션을 추가/삭제하지 말 것.
  보완은 섹션 단위 append/replace로만 한다 (그래야 diff가 잡히고 drift 추적이 가능).
  각 섹션 헤더 옆 <!-- src: ... --> 주석은 interview.json의 어느 슬롯에서 파생됐는지를 표시한다.
  인터뷰가 갱신되면 해당 src를 가진 섹션만 다시 쓴다.

  헤더의 메타 블록은 코드-매뉴얼 drift 검출(다음 단계 hook)이 읽는다. 형식을 유지할 것.
-->

# <domain> 도메인 매뉴얼

<!-- meta: drift 검출 hook이 읽는 블록. 형식 유지 -->
```yaml
domain: <domain-name>
type: <auth|crud|external_api|default>
interview_status: <in_progress|complete>
source_interview: docs/domains/<domain>/interview.json
last_synced: <YYYY-MM-DD>   # interview.json과 마지막으로 맞춘 날짜
code_paths:                  # 이 도메인을 구현하는 코드 경로 (drift 검출 기준)
  - <예: src/domains/recommendation/**>
```

## 1. 책임 범위 <!-- src: intent.in_scope, domain_map.grouping -->
이 도메인이 책임지는 것과 책임지지 않는 것. 한 문단으로 명확히.

## 2. 핵심 모델 <!-- src: data_model -->
주요 엔티티, 관계, 불변 제약, 생명주기. 표나 간단한 스키마로.

## 3. 불변 규칙 <!-- src: decisions(불변), data_model.key_constraints -->
이 도메인에서 절대 깨지면 안 되는 규칙. 각 규칙은 한 줄로 단언형.
- 예: "피부톤의 최종 진실은 skin_profile만 소유한다."

## 4. 의존하는 외부 계약 <!-- src: boundaries.dependencies, api_contract, external_deps -->
이 도메인이 의존하는 다른 도메인/외부 서비스와 그 계약. 의존 방향을 명시.
- 예: "recommendation ← skin_profile(확정 톤), catalog(검증 제품). 단방향."

## 5. 결정과 근거 <!-- src: decisions(rationale, resolved_conflict) -->
왜 이렇게 설계했는지. 특히 거스르면 안 되는 이유. 6개월 뒤 누가 되돌리려 할 때 막아주는 섹션.
| 결정 | 근거 | 거스르면 생기는 문제 |
|------|------|---------------------|
| 예: 카탈로그 독립 도메인 | 추천 입력 신뢰성 | 추천이 미검증 데이터에 오염 |

## 6. 알려진 함정 <!-- src: open_questions, contradiction-patterns로 잡힌 항목 -->
인터뷰 중 드러난 모순/경계 케이스와 그 처리. 미해결 항목은 ⚠️로 표시.

## 7. 미해결 항목 <!-- src: open_questions(blocks_completion) -->
아직 정해지지 않아 구현 전 확정이 필요한 것. 비어 있어야 이상적.
