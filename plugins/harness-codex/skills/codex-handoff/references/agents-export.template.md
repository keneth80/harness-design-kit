# AGENTS.override.md — <domain> 도메인

> 이 파일은 docs/domains/<domain>/manual.md(설계 매뉴얼)에서 자동 생성됩니다.
> 직접 수정하지 마세요. 규칙을 바꾸려면 인터뷰 → 매뉴얼 → 재export 순서를 거치세요.
> source: docs/domains/<domain>/manual.md · synced: <YYYY-MM-DD> · interview_status: <complete>

이 디렉터리의 코드를 작성·수정할 때 아래 규칙을 **반드시** 따르세요.
규칙은 도메인 설계에서 확정된 것이며, 어기면 다른 도메인과의 계약이 깨집니다.

## 책임 범위
<manual §1 책임 범위>

## 핵심 모델
<manual §2 핵심 모델>

## 불변 규칙 (절대 위반 금지)
<manual §3 불변 규칙>

## 의존 계약 (방향 엄수)
<manual §4 의존하는 외부 계약>

## 구현 시 주의
- 위 "불변 규칙"을 어기는 코드는 작성하지 마세요. 특히 의존 방향과 소유권 규칙을 지키세요.
- 이 규칙에 없는 설계 결정이 필요하면, 임의로 정하지 말고 사용자에게 확인을 요청하세요
  (이 도메인은 docs/domains/<domain>/interview.json 의 결정 기록을 따릅니다).
- interview_status가 complete가 아니면 이 도메인은 아직 구현 준비가 안 된 것입니다.

<!--
  export 규칙:
  - §5 근거 / §6 함정 / §7 미해결은 구현 규칙이 아니므로 포함하지 않는다.
  - §7에 미해결(blocks_completion)이 있으면 export 자체를 보류한다.
  - code_paths 추출 시 last_synced 등 다른 메타 항목을 경로로 오인하지 말 것.
-->
