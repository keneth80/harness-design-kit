---
name: domain-manual
trigger: "매뉴얼 만들기|도메인 문서화|규칙 문서|도메인 매뉴얼|도메인 지도|interview를 문서로"
---

# Domain Manual

**언제 쓰나:** domain-interview로 인터뷰가 complete된 뒤 그 결정 기록(interview.json)을 사람·에이전트가 읽는 매뉴얼로 변환할 때. 도메인별 docs/domains/<domain>/manual.md와 최상위 docs/domains/README.md(도메인 지도)를 고정 섹션 구조로 생성한다. 인터뷰가 갱신되면 바뀐 슬롯에 해당하는 섹션만 다시 써서 diff를 잡는다. 결정의 근거와 해소된 모순을 반드시 보존한다. 인터뷰가 아직 없으면 먼저 domain-interview를 쓴다.

`interview.json`(기계용 결정 기록)을 `manual.md`(사람·에이전트용 규칙 문서)로 변환하고 유지하는 스킬.

핵심 원칙 둘:
1. **고정 섹션 구조.** 매뉴얼은 정해진 섹션만 가진다. 자유 형식 금지 — 그래야 섹션 단위 diff가 잡히고 갱신이 추적된다.
2. **근거 보존.** 결정의 `rationale`과 `resolved_conflict`를 반드시 매뉴얼에 살린다. "왜 이렇게 했는가"가 빠지면 6개월 뒤 누군가 되돌린다.

## 입력과 출력

- 도메인별 매뉴얼: `docs/domains/<domain>/interview.json` → `docs/domains/<domain>/manual.md`
- 도메인 지도: `docs/domains/_discovery/interview.json` → `docs/domains/README.md`

## 슬롯 → 섹션 매핑 (이 스킬의 핵심)

매뉴얼의 각 섹션은 interview.json의 특정 슬롯에서 파생된다. 이 매핑이 "어느 슬롯이 바뀌면 어느 섹션을 다시 쓸지"를 결정한다.

도메인 매뉴얼 (`manual.md`):
| 매뉴얼 섹션 | 파생 슬롯 |
|-------------|-----------|
| 1. 책임 범위 | intent.in_scope, domain_map.grouping |
| 2. 핵심 모델 | data_model |
| 3. 불변 규칙 | decisions(불변), data_model.key_constraints |
| 4. 의존하는 외부 계약 | boundaries.dependencies, api_contract, external_deps |
| 5. 결정과 근거 | decisions(rationale, resolved_conflict) |
| 6. 알려진 함정 | open_questions, 모순 검출로 잡힌 항목 |
| 7. 미해결 항목 | open_questions(blocks_completion) |

도메인 지도 (`README.md`):
| 지도 섹션 | 파생 슬롯 |
|-----------|-----------|
| 개요 | _discovery.intent |
| 도메인 목록 | _discovery.domain_map |
| 의존 그래프 | _discovery.boundaries(dependencies, cycles) |
| 공유 개념 | _discovery.boundaries.shared_concepts |
| 경계 결정 이력 | _discovery.decisions |

## 워크플로우

### 최초 생성
1. 대상 `interview.json`을 **Read** 한다.
2. `interview_status`가 `complete`가 아니면 경고한다: 미완성 인터뷰로 매뉴얼을 만들면 미해결 항목이 그대로 들어간다. 진행은 하되 7번 섹션에 미해결을 명시.
3. 해당 템플릿을 복사한다 (`references/manual.template.md` 또는 `references/domain-map.template.md`).
4. 슬롯→섹션 매핑에 따라 각 섹션을 채운다. **5번(결정과 근거) 섹션은 절대 비우지 않는다** — decisions의 rationale과 resolved_conflict를 표로 옮긴다.
5. 메타 블록의 `last_synced`를 오늘 날짜로, `code_paths`는 알면 채우고 모르면 placeholder로 둔다.

### 지속적 갱신 (다듬기)
인터뷰가 바뀐 뒤 다시 호출되면:
1. `interview.json`과 기존 `manual.md`를 **둘 다 Read** 한다.
2. interview.json에서 마지막 `last_synced` 이후 바뀐 슬롯을 파악한다. (decisions 추가, 슬롯 필드 변경 등)
3. **바뀐 슬롯에 매핑된 섹션만** 다시 쓴다. 나머지 섹션은 손대지 않는다 (불필요한 diff 방지).
4. 섹션 교체는 헤더(`## N. 제목`)부터 다음 헤더 전까지를 replace 한다. 고정 섹션이라 경계가 명확하다.
5. `last_synced`를 갱신한다.

### 도메인 지도 동기화
- 개별 도메인 매뉴얼이 새로 생기거나 사라지면 README.md의 "도메인 목록"을 갱신한다.
- _discovery의 boundaries가 바뀌면 의존 그래프와 공유 개념을 다시 쓴다.

## 하지 말 것
- 섹션을 추가/삭제하거나 순서를 바꾸지 말 것 — diff 추적이 깨진다.
- 결정과 근거(5번) 섹션을 비우거나 결론만 적지 말 것 — rationale과 resolved_conflict가 핵심 자산이다.
- 갱신 시 안 바뀐 섹션을 다시 쓰지 말 것 — 노이즈 diff를 만든다.
- interview.json을 거치지 않고 매뉴얼을 임의로 편집하지 말 것 — 매뉴얼은 인터뷰의 파생물이다. 새 결정은 인터뷰에 먼저 반영.

## 참고 파일
- `references/manual.template.md` — 도메인별 매뉴얼 고정 템플릿.
- `references/domain-map.template.md` — 최상위 도메인 지도 템플릿.
