---
name: init
description: 현재 프로젝트에 하네스 워크플로우(편집 후 검증, 코드맵, 드리프트 가드)를 켠다. harness.config.json과 CLAUDE.md 하네스 구역, CONTEXT.md, 학습 기록 파일을 만들고 v1 하네스 잔재를 정리한다.
when_to_use: 하네스 켜기, 하네스 초기화, 이 프로젝트에 하네스 적용, v1 하네스에서 옮기기, harness init.
argument-hint: "[--dry-run]"
disable-model-invocation: true
---

# 하네스 초기화

보안 게이트는 플러그인을 설치한 순간부터 모든 프로젝트에서 이미 동작한다.
이 스킬은 **이 프로젝트에서만** 워크플로우 기능을 켠다. 여러 번 실행해도 안전하다(있는 파일은 건드리지 않고, CLAUDE.md의 하네스 구역만 최신으로 갱신).

## 1. 미리보기

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init_project.py" --project "$PWD" --dry-run
```

결과를 사용자에게 보여주고 진행할지 묻는다. 인자에 `--dry-run`이 있으면 여기서 끝낸다.

## 2. 적용

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init_project.py" --project "$PWD"
```

`harness.config.json` 생성은 하네스 설정 파일 변경이라 확인 창이 한 번 뜰 수 있다. 정상이다.

## 3. 프로젝트에 맞게 조정 (사용자와 짧게 상의)

- **검증 명령**: `harness.config.json`의 `verify`가 비어 있으면 자동감지(package.json 스크립트, ruff/mypy, cargo, go)로 돈다.
  자동감지가 틀리면 `{"lint": "...", "typecheck": "...", "test": "...", "run_on": ["*.ts"]}`처럼 적는다.
- **drift_guard**: 도메인 설계 사이클을 쓸 계획이 없으면 그대로 둬도 된다(docs/domains/가 없으면 아무것도 안 함).
  UI처럼 만들면서 설계가 잡히는 영역은 `warn_paths`에 넣는다.
- **CLAUDE.md**: 하네스 구역 밖에 프로젝트 개요(스택, 실행 방법, 디렉터리 구조)를 사용자와 함께 채운다.

## 4. v1 하네스 정리 (출력에 `!` 줄이 있을 때만)

v1(템플릿 복사 방식) 흔적이 있으면 플러그인 훅과 **이중으로** 돌 수 있다. 사용자 확인을 받고 정리한다.

1. `.claude/settings.json`에서 `.claude/hooks/*.py`를 부르는 `hooks` 항목을 지운다. 다른 설정은 그대로 둔다.
2. `.claude/hooks/`의 v1 스크립트, `.claude/profiles/`, `.claude/verifier-scripts/`, `.claude/reports/`를 지운다.
3. `.claude/agents/`, `.claude/skills/`, `.claude/commands/` 중 플러그인과 이름이 같은 v1 사본(code-verifier, domain-interview, verify 등)을 지운다.
   **프로젝트 전용으로 만든 스킬·규칙(예: chatbot-ui, design-system, .claude/rules/)은 남긴다.**
4. `.claudeignore`는 Claude Code가 읽지 않는 파일이라 지워도 된다.
5. 정리 후 `git status`로 변경을 보여주고 커밋 여부는 사용자에게 맡긴다.

## 5. 마무리 안내

- 풀 사이클 팀이 필요하면: `claude plugin enable harness-full@harness-design-kit --scope local`
- Claude 설계 + Codex 구현 분업이면: `claude plugin enable harness-codex@harness-design-kit --scope local`
- 다음 할 일: 새 도메인이면 `domain-interview`, 기존 코드면 `/harness-core:codemap`으로 지도부터 만든다.
