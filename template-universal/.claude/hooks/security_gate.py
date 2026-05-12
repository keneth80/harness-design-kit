#!/usr/bin/env python3
"""PreToolUse Hook — 위험 명령 정적 차단 (LLM 불필요, 0ms 지연)"""

import json, re, sys
from datetime import datetime, timezone

AUDIT_LOG = "/tmp/claude-verifier-audit.jsonl"

BLOCK_PATTERNS = [
    (r"rm\s+(-[rfRF]+\s+)?(/|~|\$HOME)", "루트/홈 삭제"),
    (r"rm\s+-[rfRF]*\s+\*", "와일드카드 삭제"),
    (r"chmod\s+(-R\s+)?777", "777 권한"),
    (r"curl\s+.*\|\s*(bash|sh)", "원격 스크립트 파이프 실행"),
    (r"wget\s+.*\|\s*(bash|sh)", "원격 스크립트 파이프 실행"),
    (r"nc\s+-[le]", "netcat 리스너"),
    (r"cat\s+.*(\.env|credentials|\.pem|\.key)\b", "시크릿 파일 읽기"),
    (r"DROP\s+(TABLE|DATABASE)", "DB 삭제"),
    (r"DELETE\s+FROM\s+\w+\s*;?\s*$", "WHERE 없는 DELETE"),
    (r":(){ :\|:& };:", "포크 폭탄"),
    (r"shutdown|reboot|poweroff", "시스템 종료"),
    (r"mkfs\.|dd\s+.*of=/dev/", "디스크 파괴"),
]

def log_event(event, command, result, reason=""):
    try:
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(), "hook": "security_gate",
                "event": event, "command": command[:500], "result": result, "reason": reason,
            }, ensure_ascii=False) + "\n")
    except: pass

def main():
    try:
        data = json.loads(sys.stdin.read())
    except:
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    cmd = data.get("tool_input", {}).get("command", "")
    if not cmd:
        sys.exit(0)

    for pattern, desc in BLOCK_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            log_event("BLOCKED", cmd, "blocked", desc)
            print(f"🛑 보안 차단: {desc}\n명령: {cmd[:200]}", file=sys.stderr)
            sys.exit(2)

    log_event("PASSED", cmd, "passed")
    sys.exit(0)

if __name__ == "__main__":
    main()
