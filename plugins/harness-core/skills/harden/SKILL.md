---
name: harden
description: 하네스 훅 위에 Claude Code 자체 보호(권한 deny 규칙, 샌드박스)와 시크릿 주입 패턴을 더하는 방법을 안내하고, 사용자가 원하면 ~/.claude/settings.json에 적용한다.
when_to_use: 보안 강화, 샌드박스, 시크릿 보호 더 단단하게, .env 읽기 원천 차단.
disable-model-invocation: true
---

# 보안 강화 (선택)

하네스 게이트는 "에이전트가 하려는 일"을 보고 막는 층이다. 그 아래에 Claude Code가 직접 강제하는 층을 하나 더 두면 우회 여지가 줄어든다.
각 단계는 사용자에게 보여주고 동의를 받은 뒤에만 적용한다.

## 1. 권한 deny 규칙 (Claude Code 네이티브)

`~/.claude/settings.json`의 `permissions.deny`에 아래를 병합한다(기존 항목은 유지).

```json
{
  "permissions": {
    "deny": [
      "Read(.env)", "Read(.env.*)", "Read(!.env.example)",
      "Read(**/*.pem)", "Read(**/*.key)", "Read(~/.ssh/**)", "Read(~/.aws/credentials)"
    ]
  }
}
```

설정 파일 수정이라 file_gate가 확인을 한 번 요청한다.

## 2. 샌드박스

Claude Code의 `/sandbox`를 켜면 Bash 명령이 허용된 디렉터리와 도메인 안에서만 돈다.
하네스의 bash_gate가 명령 문자열을 해석하는 방식이라면, 샌드박스는 OS 수준에서 막는다. 둘은 겹쳐 쓴다.

## 3. 시크릿을 값이 아니라 참조로 (권장 패턴)

에이전트가 비밀값을 아예 갖지 않게 하려면 `.env`에 실제 값 대신 참조를 둔다.

```bash
# .env — 값이 아니라 참조만 있으므로 노출돼도 무해
OPENAI_API_KEY=op://dev/openai/credential
```

실행할 때 비밀 관리 도구가 경계에서 값을 끼워 넣는다: `op run --env-file=.env -- npm run dev` (1Password CLI). Doppler, Infisical도 같은 방식이다.
에이전트는 명령을 실행할 수 있지만 키 자체는 보지 못한다.

## 4. 의도 검사

에이전트 행동이 사용자 요청과 맞는지 따로 판정하는 분류기가 필요하면 Claude Code의 auto 권한 모드를 쓴다.
하네스는 같은 일을 다시 만들지 않는다.
