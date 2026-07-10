---
name: code-review
description: 코드 이해용 워크스루. 마지막 리뷰 이후의 변경을 오너가 이해할 수 있게 설명한다 — 의도 순서 요약, 읽기 가이드, 도메인 매뉴얼 대응, 위험 지점, 이해 확인 질문. 버그 찾기(/verify)·보안(/security-review)과 다른 이해 전용 레이어.
---

코드 이해 워크스루를 시작합니다. **`.claude/skills/code-walkthrough/SKILL.md`의 방법론을 따르세요.**

## 절차

1. **범위 결정**:
   - 인자가 있으면 그 범위(도메인명, 경로, 또는 커밋 범위)로 한정.
   - 없으면 `docs/reviews/last-review.json`의 `last_commit..HEAD` diff + 워킹 트리 변경.
   - last-review.json이 없으면 워킹 트리 diff(`git diff HEAD`), 그것도 비면 최근 커밋 1개.

2. **워크스루 작성** (스킬의 5부 구조: 의도 순서 요약 → 읽기 가이드 → 도메인 연결 →
   위험한 곳 2~3 → 이해 확인 질문 3). 대화에 직접 출력하고,
   같은 내용을 `docs/reviews/<YYYY-MM-DD>-<범위>.md`에도 저장한다.

3. **매뉴얼에 없는 결정을 발견하면** 워크스루의 "도메인 연결" 절에 표면화하고,
   domain-interview/domain-manual 반영을 권한다.

4. **시점 갱신**: `docs/reviews/last-review.json`을 현재 HEAD로 갱신
   (`{"last_commit", "reviewed_at", "scope"}`).

5. **문답 대기**: 산출물이 끝이 아니다. 오너의 후속 질문에 파일:라인을 인용해 이어서 답한다.
   이해 확인 질문의 답은 오너가 요청할 때만 공개한다.

> 범위가 커밋 20개 이상이면 먼저 "이해 부채가 밀려 있다"고 알리고,
> 결정 단위로 2~3회에 나눠 리뷰할 것을 제안한다.
