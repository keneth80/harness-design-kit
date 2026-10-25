"""하네스 훅 공통 라이브러리.

원본은 plugins/harness-core/scripts/_lib.py 하나뿐이다.
다른 플러그인의 사본은 `python3 tools/sync_lib.py`로 덮어쓰며, 직접 수정하지 않는다.
(플러그인은 서로의 디렉터리를 참조할 수 없어서 사본이 필요하다.)

훅 계약
  - 입력: stdin JSON (tool_name, tool_input, cwd, hook_event_name, ...)
  - 결정: PreToolUse는 hookSpecificOutput.permissionDecision(deny/ask)을 JSON으로 낸다.
  - 문맥 주입: hookSpecificOutput.additionalContext (모델이 읽는다)
  - 예외가 나도 작업을 막지 않는다(fail-open). 단 보안 게이트는 판정 로직 자체가 실패하면
    해당 호출만 통과시키고 감사 로그에 error로 남긴다.
"""
import datetime
import fnmatch
import hashlib
import json
import os
import sys

CONFIG_FILE = "harness.config.json"
USER_CONFIG = os.path.join(os.path.expanduser("~"), ".claude", "harness.config.json")

DEFAULT_CONFIG = {
    "version": 2,
    "drift_guard": {"mode": "block", "warn_paths": []},
    "verify": {},
    "security": {
        # 에이전트가 읽거나 Bash로 건드리면 안 되는 시크릿 파일 (glob, 파일명 또는 상대경로)
        "secret_paths": [
            ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa", "id_ed25519",
            ".netrc", ".npmrc", ".pypirc", "credentials", "credentials.json",
            "service-account*.json", ".aws/credentials", ".ssh/*",
        ],
        # secret_paths에 걸려도 허용할 예외 (예시 파일)
        "allow_paths": [".env.example", ".env.sample", ".env.template", "*.example", "*.sample"],
        # 시크릿 외부 전송 의심 명령: ask(확인) | deny(차단)
        "exfil": "ask",
        # 하네스 설정 파일 수정: ask | deny
        "config_edits": "ask",
    },
    "codemap": {"enabled": True},
    "backpressure": {"enabled": True},
}


# ── 입력 ────────────────────────────────────────────────────────────────

def read_event():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}


def project_dir(event):
    return (os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd())


def tool_target(event):
    """Write/Edit/Read 계열의 대상 경로. 도구마다 키가 달라 관대하게 찾는다."""
    ti = event.get("tool_input") or {}
    return (ti.get("file_path") or ti.get("path") or ti.get("notebook_path")
            or ti.get("filePath") or "")


def written_text(event):
    """이번 호출로 새로 쓰이는 텍스트만 모은다 (Write content / Edit new_string / MultiEdit edits)."""
    ti = event.get("tool_input") or {}
    parts = []
    for key in ("content", "file_text", "new_string", "new_str", "new_source"):
        val = ti.get(key)
        if isinstance(val, str) and val:
            parts.append(val)
    for edit in ti.get("edits") or []:
        if isinstance(edit, dict):
            val = edit.get("new_string") or edit.get("new_str") or ""
            if val:
                parts.append(val)
    return "\n".join(parts)


def abspath_in(base, path):
    if not path:
        return ""
    path = os.path.expanduser(path)
    return os.path.normpath(path if os.path.isabs(path) else os.path.join(base, path))


def relpath_or_none(path, base):
    try:
        rel = os.path.relpath(path, base)
    except ValueError:
        return None
    return None if rel.startswith("..") else rel


# ── 설정 ────────────────────────────────────────────────────────────────

def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _merge(base, over):
    out = dict(base)
    for key, val in (over or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], val)
        else:
            out[key] = val
    return out


def is_initialized(proj):
    """하네스가 init된 프로젝트인지. 워크플로우 훅(검증·코드맵·백프레셔)은 여기서만 돈다."""
    return os.path.isfile(os.path.join(proj, CONFIG_FILE))


def load_config(proj):
    """기본값 < ~/.claude/harness.config.json < 프로젝트 harness.config.json 순으로 병합.

    v1 설정(profile 필드, drift_guard만 있는 파일)도 그대로 읽힌다.
    v1의 .claude/verify.json이 있으면 verify 섹션이 비어 있을 때 대신 쓴다.
    """
    cfg = _merge(DEFAULT_CONFIG, _read_json(USER_CONFIG))
    cfg = _merge(cfg, _read_json(os.path.join(proj, CONFIG_FILE)))
    if not cfg.get("verify"):
        legacy = _read_json(os.path.join(proj, ".claude", "verify.json"))
        if legacy:
            cfg["verify"] = legacy
    return cfg


# ── 경로 매칭 ──────────────────────────────────────────────────────────

def glob_match(path, patterns):
    """경로가 패턴 중 하나에 맞는지. 파일명 단독 패턴은 basename에도 맞춘다.

    `dir/**`와 `dir/`는 그 아래 전체, `*`는 fnmatch 규칙대로 `/`도 넘는다.
    """
    if not path:
        return False
    norm = path.replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    base = os.path.basename(norm)
    for pat in patterns or []:
        pat = (pat or "").strip().replace("\\", "/")
        if not pat:
            continue
        if pat.endswith("/"):
            pat += "**"
        if pat.endswith("/**") and (norm == pat[:-3] or norm.startswith(pat[:-2])):
            return True
        if fnmatch.fnmatch(norm, pat) or fnmatch.fnmatch(norm, "*/" + pat):
            return True
        if "/" not in pat and fnmatch.fnmatch(base, pat):
            return True
    return False


def protected_plugin_roots():
    """에이전트가 수정하면 안 되는 플러그인 디렉터리.

    하네스 자체를 개발할 때는 HARNESS_DEV=1로 Claude Code를 실행하면 이 보호가 풀린다.
    (훅은 Claude Code 프로세스의 환경을 물려받으므로 에이전트가 Bash로 이 값을 켤 수는 없다.)
    """
    if os.environ.get("HARNESS_DEV", "").strip() in ("1", "true", "on"):
        return []
    roots = [os.environ.get("CLAUDE_PLUGIN_ROOT"),
             os.path.join(os.path.expanduser("~"), ".claude", "plugins")]
    return [os.path.normpath(r) for r in roots if r]


def is_plugin_path(full):
    return any(full == r or full.startswith(r + os.sep) for r in protected_plugin_roots())


def is_protected_config(full, proj):
    home = os.path.expanduser("~")
    return full in {
        os.path.join(proj, CONFIG_FILE),
        os.path.join(proj, ".claude", "settings.json"),
        os.path.join(proj, ".claude", "settings.local.json"),
        os.path.join(home, ".claude", "settings.json"),
        os.path.join(home, ".claude", CONFIG_FILE),
    }


def is_secret_path(path, cfg):
    sec = cfg.get("security") or {}
    if glob_match(path, sec.get("allow_paths")):
        return False
    return glob_match(path, sec.get("secret_paths"))


# ── 출력 ────────────────────────────────────────────────────────────────

def _emit(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def decide(decision, reason, event_name="PreToolUse"):
    """PreToolUse 권한 결정 (deny | ask). allow는 권한 체계를 우회하므로 내지 않는다."""
    _emit({
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    })
    sys.exit(0)


def add_context(text, event_name, user_message=None):
    """모델 컨텍스트에 문장을 주입한다. user_message가 있으면 사용자 화면에도 띄운다."""
    payload = {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": text}}
    if user_message:
        payload["systemMessage"] = user_message
    _emit(payload)


def block_stop(reason):
    """Stop 훅에서 종료를 막고 재작업을 요구한다."""
    _emit({"decision": "block", "reason": reason})
    sys.exit(0)


# ── 감사 로그 ──────────────────────────────────────────────────────────

def data_dir():
    """플러그인 업데이트에도 유지되는 저장소. 훅 밖(테스트)에서는 ~/.claude/harness-data."""
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(
        os.path.expanduser("~"), ".claude", "harness-data")
    os.makedirs(base, exist_ok=True)
    return base


def monitor_enabled():
    return os.environ.get("HARNESS_MONITOR", "").strip().lower() in ("1", "true", "on", "yes")


def audit(proj, hook, result, target="", reason=""):
    """deny/ask/block/error는 항상, pass/warn은 HARNESS_MONITOR=1일 때만 기록한다.

    로그는 프로젝트 밖(플러그인 데이터 디렉터리)에 쌓이므로 에이전트 작업 영역을 오염시키지 않는다.
    """
    always = result in ("deny", "ask", "block", "error")
    if not always and not monitor_enabled():
        return
    if os.environ.get("HARNESS_NO_AUDIT"):
        return
    try:
        entry = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "project": proj,
            "hook": hook,
            "result": result,
            "target": (target or "")[:300],
            "reason": (reason or "")[:500],
        }
        with open(os.path.join(data_dir(), "audit.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def short_hash(text):
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:10]
