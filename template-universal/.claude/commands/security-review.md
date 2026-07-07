---
name: security-review
description: security-reviewer 에이전트를 호출하여 논리적 보안 취약점(권한 검증 누락, IDOR, Supabase RLS 구멍, mass assignment)을 점검한다. 기능 완료 후·배포 전 실행 권장. 읽기 전용 — 리포트만 생성.
---

보안 리뷰를 시작합니다.

## 절차

1. 점검 범위 결정:
   - 인자가 있으면 그 범위(도메인명 또는 경로)로 한정.
   - 없으면 현재 브랜치의 변경 파일(`git diff --name-only` 기준)과 그 파일이 속한 도메인.

2. security-reviewer 에이전트에게 위임:
   - "security-reviewer를 호출하여 <범위>의 논리적 취약점을 점검해주세요"
   - 에이전트는 opus 모델로 동작하며 `.claude/skills/security-review/SKILL.md`의
     방법론(권한 매트릭스, IDOR 점검)과 스택 체크리스트(Supabase RLS, Next.js, FastAPI)를 따른다.

3. 결과는 `docs/security-review-<날짜>.md`에 저장된다.
   critical/high 발견 시 배포 보류 권고가 표시된다.

> 역할 분담: 시크릿 유출은 secret_scan 훅(자동), 위험 bash 명령은 security_gate 훅(자동),
> **권한 모델·논리 취약점은 이 커맨드(온디맨드)**가 담당한다.
