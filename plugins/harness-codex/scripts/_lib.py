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
import hmac
import json
import os
import re
import subprocess
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
    # 루프 안전장치 (init한 프로젝트에서만). 시험지를 고쳐서 통과하는 것을 막는다
    "loop": {
        "protect_tests": True,
        # 테스트 파일: 약하게 만드는 변경(skip 추가, 단언·테스트 줄이기, 삭제)만 ask
        "test_paths": ["tests/**", "test/**", "__tests__/**", "spec/**", "test_*.py", "*_test.py", "conftest.py",
                       "*.test.*", "*.spec.*", "*_test.go", "*Test.java", "*Tests.java", "*Test.kt", "*Tests.kt",
                       "*Tests.cs", "*Test.cs", "*_spec.rb", "*Spec.scala", "*Test.php", "*Tests.swift",
                       "*_test.dart", "*_test.exs"],
        # 동결 파일: 정답 데이터라 어떤 수정이든 ask (사람이 정한 기대값). 이름만으로 확실한 것만 기본값으로 두고,
        # expected/·baseline/ 같은 폴더는 입력 데이터일 수도 있어 loop_setup.py가 후보로 제안한다
        "frozen": ["golden/**", "__snapshots__/**", "*.snap", "*.golden", "*.golden.*", "*.approved.*"],
    },
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
    if is_ledger_key(path):
        return True  # 원장 서명 키. allow_paths로도 풀 수 없다
    sec = cfg.get("security") or {}
    if glob_match(path, sec.get("allow_paths")):
        return False
    return glob_match(path, sec.get("secret_paths"))


# ── 출력 ────────────────────────────────────────────────────────────────

def _emit(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def decide(decision, reason, event_name="PreToolUse", user_message=None):
    """PreToolUse 권한 결정 (deny | ask). allow는 권한 체계를 우회하므로 내지 않는다."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    if user_message:
        payload["systemMessage"] = user_message
    _emit(payload)
    sys.exit(0)


def gate_error(proj, hook, target, exc):
    """보안 게이트의 판정 로직이 실패했을 때. 조용히 통과시키지 않고 사용자 확인(ask)으로 돌린다.

    고장 난 판독기 앞에서 문을 그냥 열어 주지 않고 사람을 부르는 것과 같다. 오류는 드물어서 평소 흐름은
    거의 막히지 않고, 업데이트 버그로 모든 판정이 실패하면 확인 창이 이어져 바로 눈에 띈다.
    """
    audit(proj, hook, "error", target, repr(exc))
    decide("ask",
           f"[harness] {hook}가 판정 중 오류({type(exc).__name__})로 이 작업을 검사하지 못했습니다. "
           "내용을 직접 확인하고 허용할지 정하세요.",
           user_message=f"harness: {hook} 판정 오류로 확인을 요청합니다. 반복되면 /harness-core:audit로 확인하세요.")


def recent_errors(since_ts, limit_lines=5000):
    """since_ts(epoch 초) 이후 감사 로그의 error 항목. 파일 끝부분만 읽는다."""
    path = os.path.join(data_dir(), "audit.jsonl")
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()[-limit_lines:]
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            e = json.loads(line)
            if e.get("result") != "error":
                continue
            ts = datetime.datetime.fromisoformat(e["ts"]).timestamp()
        except Exception:
            continue
        if ts > since_ts:
            out.append(e)
    return out


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


# ── 루프 안전장치: 통과 기록 원장 ────────────────────────────────────
#
# 에이전트가 "통과했다"고 말하는 것 대신, 스크립트가 직접 돌린 검사 결과를 서명해서 남긴다.
# 학생이 써낸 "다 맞았어요"가 아니라 채점기가 찍은 도장을 믿는 셈이다.
#   - 원장: <프로젝트>/.harness/verify-ledger.json (에이전트는 쓸 수 없음, file_gate·bash_gate가 막음)
#   - 서명 키: ~/.claude/harness-data/ledger.key (에이전트는 읽을 수 없음). 원장을 손으로 고치면 서명이 깨진다
#   - 지문: git HEAD + 작업 트리 상태. 원장 이후 코드가 바뀌면 stale

LEDGER_DIR = ".harness"
LEDGER_FILE = "verify-ledger.json"
CHECK_KEYS = ("lint", "typecheck", "test")


def ledger_path(proj):
    return os.path.join(proj, LEDGER_DIR, LEDGER_FILE)


def ledger_key_path():
    # 플러그인마다 CLAUDE_PLUGIN_DATA가 달라서, 모든 하네스 플러그인이 같이 쓰는 고정 위치에 둔다
    return os.path.join(os.path.expanduser("~"), ".claude", "harness-data", "ledger.key")


def _norm(path):
    return os.path.normpath(os.path.abspath(os.path.expandvars(os.path.expanduser(path))))


def is_ledger_key(path):
    return bool(path) and _norm(path) == _norm(ledger_key_path())


def is_ledger_path(full, proj):
    """에이전트가 쓰면 안 되는 원장 파일과 서명 키."""
    return bool(full) and (_norm(full) == _norm(ledger_path(proj)) or is_ledger_key(full))


def _ledger_key(create=False):
    path = ledger_key_path()
    try:
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
            if key:
                return key.encode()
    except OSError:
        pass
    if not create:
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    key = os.urandom(32).hex()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(key)
    return key.encode()


def _sign(body, key):
    canon = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hmac.new(key, canon.encode("utf-8"), hashlib.sha256).hexdigest()


# 하네스가 스스로 만드는 산출물. 이것이 바뀌었다고 검사 결과가 낡지는 않는다
FINGERPRINT_IGNORE = [LEDGER_DIR + "/**", "docs/codemap.md", "docs/verification-report.md", "_workspace/**",
                      ".claude/settings.local.json"]


def tree_fingerprint(proj, cfg=None):
    """git HEAD + 작업 트리 상태(+수정 시각). 하네스 산출물(원장, 코드맵, 검증 리포트 등)은 제외한다.
    loop.fingerprint_ignore로 프로젝트의 생성물을 더 뺄 수 있다."""
    ignore = FINGERPRINT_IGNORE + list(((cfg or {}).get("loop") or {}).get("fingerprint_ignore") or [])
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=proj, capture_output=True,
                              text=True, timeout=10).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=proj,
                                capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if status.returncode != 0:
        return None
    digest = hashlib.sha1()
    digest.update(head.encode())
    for line in sorted(status.stdout.splitlines()):
        path = line[3:].split(" -> ")[-1].strip('"')
        if glob_match(path, ignore):
            continue
        digest.update(line.encode("utf-8", "replace"))
        try:
            digest.update(str(os.path.getmtime(os.path.join(proj, path))).encode())
        except OSError:
            pass
    return digest.hexdigest()


def autodetect_checks(proj):
    has = lambda f: os.path.exists(os.path.join(proj, f))  # noqa: E731
    if has("package.json"):
        try:
            with open(os.path.join(proj, "package.json"), encoding="utf-8") as f:
                scripts = (json.load(f) or {}).get("scripts") or {}
        except Exception:
            scripts = {}
        cfg = {}
        for name in ("typecheck", "type-check"):
            if name in scripts:
                cfg["typecheck"] = f"npm run -s {name}"
                break
        else:
            if has("tsconfig.json"):
                cfg["typecheck"] = "npx --no-install tsc --noEmit"
        if "lint" in scripts:
            cfg["lint"] = "npm run -s lint"
        if "test" in scripts:
            cfg["test"] = "npm test --silent"
        return cfg
    if has("pyproject.toml") or has("setup.py") or has("requirements.txt"):
        return {"test": "python3 -m pytest -q -x"} if (has("tests") or has("test")) else {}
    if has("Cargo.toml"):
        return {"typecheck": "cargo check -q", "test": "cargo test -q"}
    if has("go.mod"):
        return {"typecheck": "go vet ./...", "test": "go test ./..."}
    return {}


def verify_checks(proj, cfg):
    """[(이름, 명령)], 타임아웃. harness.config.json의 verify가 비어 있으면 자동 감지."""
    vcfg = dict(cfg.get("verify") or {})
    if not any(vcfg.get(k) for k in CHECK_KEYS):
        vcfg = {**autodetect_checks(proj), "timeout": vcfg.get("timeout", 180)}
    return [(k, vcfg[k]) for k in CHECK_KEYS if vcfg.get(k)], int(vcfg.get("timeout", 180))


def write_ledger(proj, results, cfg=None):
    """results: [{name, command, exit, seconds, tail}]. 검사가 끝난 뒤의 트리 지문으로 서명해 남긴다."""
    body = {
        "version": 1,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "fingerprint": tree_fingerprint(proj, cfg),
        "checks": results,
        "passed": bool(results) and all(r.get("exit") == 0 for r in results),
    }
    body["sig"] = _sign(body, _ledger_key(create=True))
    d = os.path.join(proj, LEDGER_DIR)
    os.makedirs(d, exist_ok=True)
    ignore = os.path.join(d, ".gitignore")
    if not os.path.exists(ignore):  # 원장은 커밋하지 않는다 (사용자 .gitignore를 건드리지 않음)
        with open(ignore, "w", encoding="utf-8") as f:
            f.write("*\n")
    tmp = ledger_path(proj) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ledger_path(proj))
    return body


def ledger_status(proj, cfg):
    """원장 상태. state:
    pass         설정된 검사를 모두 통과했고, 그 뒤로 코드가 바뀌지 않았다
    partial-pass 통과했지만 설정된 검사 전부는 아니다 (예: --cmd로 한 명령만)
    fail         가장 최근 검사가 실패했다
    stale        원장 이후 코드가 바뀌었다 (다시 돌려야 함)
    tampered     서명이 맞지 않는다 (누군가 원장을 손으로 고쳤다)
    missing      원장이 없다
    unconfigured 검증 명령이 없다
    """
    expected, _ = verify_checks(proj, cfg)
    if not expected:
        return {"state": "unconfigured"}
    try:
        with open(ledger_path(proj), encoding="utf-8") as f:
            body = json.load(f)
    except (OSError, ValueError):
        return {"state": "missing", "expected": [k for k, _ in expected]}
    sig = body.pop("sig", "")
    key = _ledger_key()
    if not key or not hmac.compare_digest(sig, _sign(body, key)):
        return {"state": "tampered"}
    checks = body.get("checks") or []
    summary = [{"name": c.get("name"), "command": c.get("command"), "exit": c.get("exit")} for c in checks]
    base = {"created": body.get("created"), "checks": summary}
    fp = tree_fingerprint(proj, cfg)
    if not fp or body.get("fingerprint") != fp:
        return {"state": "stale", **base}
    if not body.get("passed"):
        return {"state": "fail", **base}
    ran = {(c.get("name"), c.get("command")) for c in checks}
    complete = all((k, cmd) in ran for k, cmd in expected)
    return {"state": "pass" if complete else "partial-pass", **base}


# ── 루프 안전장치: 시험지 보호 ───────────────────────────────────────

SKIP_RE = re.compile(
    r"\.skip\s*\(|\bx(?:it|describe|test)\s*\(|\.only\s*\(|\b(?:it|test)\.todo\b"
    r"|@pytest\.mark\.(?:skip|skipif|xfail)\b|\bpytest\.(?:skip|xfail)\s*\(|@unittest\.skip"
    r"|\.skipTest\s*\(|\bt\.Skip(?:f|Now)?\s*\(|#\[ignore\]|@Disabled\b|@Ignore\b"
    r"|\[Ignore\]|\bSkip\s*=\s*\"|\bmarkTestSkipped\s*\(")
ASSERT_RE = re.compile(
    r"\bassert\w*\b|\bAssert\.\w+|\bexpect\s*\(|\.should\b|\bt\.(?:Error|Errorf|Fatal|Fatalf|Fail)\s*\("
    r"|\brequire\.\w+\s*\(|\bassert_\w*!?\s*\(")
TESTDEF_RE = re.compile(
    r"^\s*(?:async\s+)?def\s+test\w*\s*\(|\b(?:it|test)\s*\(\s*['\"`]|^\s*func\s+Test\w*\s*\("
    r"|#\[test\]|@Test\b", re.M)


def tests_protected(proj, cfg):
    return is_initialized(proj) and bool((cfg.get("loop") or {}).get("protect_tests", True))


def test_kind(full, proj, cfg):
    """'frozen' | 'test' | None. 프로젝트 밖 경로는 보지 않는다."""
    rel = os.path.relpath(_norm(full), _norm(proj))
    if rel.startswith(".."):
        return None
    loop = cfg.get("loop") or {}
    if glob_match(rel, loop.get("frozen")):
        return "frozen"
    if glob_match(rel, loop.get("test_paths")):
        return "test"
    return None


def weakening(old, new):
    """테스트를 약하게 만드는 변화 목록. 테스트를 늘리거나 고치는 것은 해당 없음."""
    old, new = old or "", new or ""
    out = []
    added_skips = len(SKIP_RE.findall(new)) - len(SKIP_RE.findall(old))
    if added_skips > 0:
        out.append(f"skip/only 표시 {added_skips}개 추가")
    a0, a1 = len(ASSERT_RE.findall(old)), len(ASSERT_RE.findall(new))
    if a1 < a0:
        out.append(f"단언 {a0}개 → {a1}개")
    t0, t1 = len(TESTDEF_RE.findall(old)), len(TESTDEF_RE.findall(new))
    if t1 < t0:
        out.append(f"테스트 {t0}개 → {t1}개")
    return out


def test_guard_message(path, kind, detail=""):
    if kind == "frozen":
        what = f"정답 데이터로 동결된 파일을 수정합니다 ({path})"
    else:
        what = f"테스트를 약하게 만드는 변경입니다 ({path}{': ' + detail if detail else ''})"
    return (f"{what}. 루프에서 통과하려고 시험지를 고치는 것을 막습니다. 테스트나 기대값이 정말 틀렸다면 "
            "근거를 사용자에게 설명하고, 사용자가 확인 창에서 허용하면 진행하세요. 보호 설정을 끄거나 "
            "다른 경로로 우회하지 마세요.")
