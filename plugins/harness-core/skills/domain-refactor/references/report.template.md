# 리팩토링 진단 리포트: <domain>

<!--
  매번 실행 시 생성되는 "현재 코드 vs 매뉴얼" 차이 리포트.
  docs/domains/<domain>/refactor-report.md 에 저장(덮어씀).
  위반이 줄어드는 추이를 보며 점진적으로 다듬는 용도.
  각 위반은 매뉴얼의 특정 규칙에 근거해야 한다. 근거 없는 "개선 제안"은 넣지 않는다.
-->

```yaml
domain: <domain-name>
generated: <YYYY-MM-DD>
manual: docs/domains/<domain>/manual.md
manual_last_synced: <YYYY-MM-DD>
mode: report   # report | applied
violations_found: <N>
violations_fixed: <0 또는 적용 수>
```

## 요약
규칙 대비 위반 <N>건. (전회 대비 증감이 있으면 표시)

## 위반 목록

각 항목은 [매뉴얼 규칙] → [코드 현황] → [제안된 수정]의 형태. 규칙 출처(매뉴얼 섹션)를 명시.

### V1. <한 줄 요약>
- **근거 규칙** (manual §3 불변 규칙): "<매뉴얼에 적힌 규칙 원문>"
- **위반 위치**: `src/.../file.py:123`
- **현황**: 코드가 무엇을 하고 있는지 (규칙과 어떻게 어긋나는지)
- **제안**: 어떻게 고치면 규칙에 맞는지 (구체적 변경)
- **위험도**: high(불변 규칙/의존 계약 위반) | med | low
- **자동수정 가능**: yes/no (no면 사람 판단 필요 이유)

## 범위 밖 (의도적으로 제외)
매뉴얼에 근거가 없어 이 스킬이 다루지 않는 것들. (성능 최적화, 스타일 등)
필요하면 별도로 다루되, 이 리포트의 책임이 아님을 명시.
