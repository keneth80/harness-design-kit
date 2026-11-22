---
name: slim
description: 에이전트가 보는 문서를 다이어트한다. CLAUDE.md는 규칙을 "늘 필요(남김)·강제할 것(훅·설정)·특정 작업 절차(스킬)·참고 자료(문서)·낡음"으로 나눠 옮기고, DECISIONS.md·spec·CONTEXT.md·교훈 같은 큰 문서는 AI가 읽고 지금 필요한 것만 남긴 가벼운 판으로 다시 쓴다 (원본 전체는 보관, 별도 검수, 확인 후 적용).
when_to_use: CLAUDE.md 정리, CLAUDE.md가 너무 길다, 규칙을 안 지킨다, 컨텍스트 줄이기, 스킬로 분리, 200줄, DECISIONS.md가 크다, 문서 경량화, 문서가 너무 길다, 결정 기록 정리, 스펙 나누기, 보관.
argument-hint: "[CLAUDE.md | 문서 경로 | docs]"
allowed-tools: Bash(python3 *doc_budget.py*), Bash(python3 *claude_md_audit.py*), Bash(mkdir -p docs/archive), Bash(mkdir -p .harness*), Bash(cp * docs/archive/*)
disable-model-invocation: true
---

# 문서 다이어트

먼저 크기를 본다. 매 대화에 실리는 문서(CLAUDE.md와 @import, `.claude/rules`)는 합계로, 에이전트가 자주 읽는 문서는 파일마다 잰다.
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doc_budget.py"
```
- 인자가 없거나 `CLAUDE.md`면 아래 절차대로 한다. `@`로 불러오는 파일도 매번 실리니 같이 본다.
- 인자가 다른 문서(`DECISIONS.md`, `docs/spec.md` 등)이거나 `docs`면 맨 아래 "큰 문서" 절차를 따른다 (`docs`면 기준을 넘은 문서를 큰 순서로 하나씩).

## CLAUDE.md

CLAUDE.md는 매 대화 맨 앞에 통째로 실린다. 가방에 한 달에 한 번 쓰는 물건까지 넣고 다니는 셈이고, 길수록 규칙을 덜 지킨다.
늘 쓰는 것만 남기고, 나머지는 제자리로 보낸다.

| 어디로 | 무엇을 | 왜 |
|---|---|---|
| CLAUDE.md에 남김 | 모든 작업에 늘 필요한 짧은 규칙 | 매번 읽혀야 의미가 있다 |
| 훅·하네스 설정·권한 deny | 어기면 안 되는 금지 규칙 | 부탁이 아니라 기계로 막는다. 관련 없을 때는 맥락을 차지하지 않는다 |
| 프로젝트 스킬 (`.claude/skills/`) | 특정 작업 때만 필요한 절차 | 평소엔 이름과 설명만, 필요할 때 본문을 읽는다 |
| 문서 (`docs/`) + 한 줄 링크 | 표, 긴 목록, 참고 자료 | 필요할 때 읽게 한다 |
| 삭제 후보 | 더는 맞지 않는 규칙 | 사용자가 확인한 것만 지운다 |

### 1. 진단
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude_md_audit.py"
```
- `blocks`의 `guess`는 규칙 기반 1차 추정이다. 각 묶음을 읽고 분류를 바로잡는다. 특히:
  - `covered: true`는 하네스가 이미 기계로 막는 규칙이다 (시크릿, 위험한 명령, 테스트 약화). CLAUDE.md에서 빼도 된다.
  - 코드와 다른 설명, 없는 파일·명령을 가리키는 규칙은 **낡음** 후보다. 짐작으로 판단하지 말고 실제로 확인한다 (파일 존재, package.json 스크립트 등).
  - 하네스 관리 구역(`harness:begin`~`end`)은 건드리지 않는다.
- Claude Code의 `/doctor`도 중복되거나 비대한 메모리 파일을 점검한다. 파일 단위 문제는 그쪽, 규칙 내용 분류는 여기서 한다.

### 2. 제안
사용자에게 표로 보여준다: 묶음(줄 번호), 분류, 옮길 곳, 이유. 맨 위에 "지금 N줄 → 정리 후 약 M줄".
- **강제**는 무엇으로 막을지 구체적으로: `harness.config.json`의 `security.secret_paths`·`loop.frozen`·`verify`, `.claude/settings.json`의 `permissions.deny`(예: `Bash(npm publish:*)`), 이미 하네스가 막는 것은 "삭제(하네스가 강제)".
- **스킬**은 이름(영문 kebab-case)과 언제 쓰는지 한 줄 설명을 붙인다. 비슷한 절차는 한 스킬로 묶는다.
- 사용자가 고르게 한다. 전부, 일부, 분류 수정.

### 3. 적용 (확인받은 것만)
1. 원본을 `.harness/CLAUDE.md.bak-<날짜>`로 복사해 둔다 (되돌리기용). `.harness/.gitignore`가 없으면 내용 `*`로 만들어 커밋되지 않게 한다.
2. **스킬**: `.claude/skills/<이름>/SKILL.md`를 만든다. frontmatter는 `name`, `description`(무엇을 하는지), `when_to_use`(사용자가 쓸 말). 본문은 원문을 그대로 옮긴다. 다시 쓰지 않는다.
3. **문서**: `docs/claude/<이름>.md`로 옮기고 CLAUDE.md에는 `- <주제>: docs/claude/<이름>.md` 한 줄만 남긴다.
4. **강제**: 설정 파일을 고친다 (하네스 설정·권한 변경은 확인 창이 뜬다). 강제가 확실해지면 CLAUDE.md에서 뺀다.
5. **삭제**: 사용자가 고른 것만.
6. 결과를 보고한다: 줄 수 변화, 만든 스킬·문서, 바뀐 설정, 백업 위치. 다시 진단을 돌려 남은 분류를 보여준다.

### 지킬 것
- 옮길 때 문장을 바꾸지 않는다. 의미가 바뀌면 규칙이 달라진다.
- 확인 없이 지우지 않는다.
- 사용자 전역 `~/.claude/CLAUDE.md`는 인자로 경로를 받았을 때만 다룬다.

## 큰 문서 (CLAUDE.md 말고)

AI가 읽고 판단해서 줄인다. 원본 전체는 `docs/archive/`에 그대로 보관하니 줄여도 정보는 사라지지 않고,
에이전트는 가벼워진 문서만 매번 읽는다. 큰 문서를 메인 대화에서 통째로 읽지 않도록 읽고 쓰는 일은 에이전트에게 맡긴다.

### 1. 준비
- 크기를 본다: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doc_budget.py"`
- 경로를 정한다 (날짜는 오늘, `YYYYMMDD`):
  - 원본 보관: `docs/archive/<파일 이름>-<날짜>.md`
  - 초안: `.harness/slim-draft/<파일 이름>`. `.harness/.gitignore`가 없으면 내용 `*`로 만든다
- 사용자가 바라는 게 있으면 받아 둔다 (얼마나 줄일지, 꼭 남길 것). 없으면 묻지 않고 기본대로 한다.

### 2. 초안 (doc-slimmer)
Agent 도구로 `harness-core:doc-slimmer`를 부른다 (백그라운드 아님). 프롬프트에 대상 문서, 초안 경로, 원본 보관 경로,
문서 종류(결정 기록·명세·용어·교훈·로그), 사용자가 바라는 것을 적는다.
에이전트가 항목마다 유지·압축·지난 항목·합침·확인 필요를 정해 초안만 쓴다. 원본은 아직 그대로다.

### 3. 대조 (slim-checker)
Agent 도구로 `harness-core:slim-checker`를 부르고 원본 경로와 초안 경로를 준다. 만든 쪽과 분리된 검수다.
"고칠 것"이 있으면 그 목록을 doc-slimmer에게 다시 넘겨 초안만 고치게 하고, 한 번 더 대조한다 (최대 2번).
그래도 남으면 사용자에게 그대로 보여준다.

### 4. 사용자 확인
보여줄 것: 줄 수와 토큰 변화, 유지·압축·지난 항목·합침 개수, **확인 필요** 목록, 덜어낸 것 중 아쉬울 수 있는 것, 대조 결과, 초안 경로.
사용자는 초안 파일을 열어 볼 수 있다. 바꿀 점을 말하면 doc-slimmer에게 넘겨 초안을 고친다.

### 5. 적용 (확인받은 뒤)
```bash
mkdir -p docs/archive
cp <원본> docs/archive/<파일 이름>-<날짜>.md
cp .harness/slim-draft/<파일 이름> <원본>
```
`doc_budget.py`를 다시 돌려 결과를 보고한다: 전후 크기, 보관 위치, 확인 필요로 남긴 것.
다른 문서가 이 문서의 항목 번호를 참조하면 번호가 그대로인지 확인한다.

### 지킬 것
- 확인 없이 원본을 바꾸지 않는다. 바꾸기 전에 원본 전체를 보관한다.
- 사실(결정, 수치, 이름, 날짜, 번호)은 바꾸지 않는다. 판단이 서지 않는 항목은 남기고 사용자에게 묻는다.
- 교훈(`docs/lessons-learned.md`)은 `/harness-core:lessons`의 30개 규칙과 함께 본다.
- 보관 파일은 `docs/archive/` 아래에 둔다. 이 폴더는 크기 점검에서 빠지고, 에이전트는 필요할 때만 찾아 읽는다.
