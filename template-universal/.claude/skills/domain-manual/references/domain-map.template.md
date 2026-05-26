<!--
  도메인 지도 (docs/domains/README.md)

  _discovery/interview.json 에서 파생되는 전체 도메인 개관.
  개별 도메인의 상세는 각 <domain>/manual.md 가 소유한다. 여기엔 중복 기재하지 않는다.
  domain_map / boundaries 슬롯이 갱신되면 이 파일을 다시 쓴다.
-->

# 도메인 지도

<!-- meta: 형식 유지 -->
```yaml
source_interview: docs/domains/_discovery/interview.json
discovery_status: <in_progress|complete>
last_synced: <YYYY-MM-DD>
domain_count: <N>
```

## 개요 <!-- src: intent -->
무엇을 만드는 시스템인지 한 문단. 범위(in/out)도 한 줄씩.

## 도메인 목록 <!-- src: domain_map -->
| 도메인 | 유형 | 책임 | 매뉴얼 |
|--------|------|------|--------|
| 예: recommendation | default | 확정 톤+카탈로그→제품 매칭 | [manual](./recommendation/manual.md) |

## 의존 그래프 <!-- src: boundaries.dependencies, cycles -->
도메인 간 의존 방향. 텍스트 다이어그램 또는 인접 리스트.
순환 의존은 없어야 하며, 있었다면 어떻게 끊었는지 명시.
```
예:
auth → (모두의 기반)
skin_analysis → skin_profile (톤 제안)
recommendation ← skin_profile, catalog
community ← catalog(제안), recommendation(읽기, 단방향)
```

## 공유 개념 <!-- src: boundaries.shared_concepts -->
여러 도메인에 걸친 개념과 그 소유 도메인. 소유권을 명확히 해 정의 불일치를 막는다.
- 예: "사용자 피부톤 → skin_profile 소유. analysis는 후보만 제안."

## 경계 결정 이력 <!-- src: decisions(domain_map, boundaries) -->
도메인을 어떻게 나눴고 왜 그렇게 나눴는지. 경계 모순을 어떻게 해소했는지.
