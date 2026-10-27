#!/usr/bin/env python3
"""verify_guard: PostToolUse(Write|Edit|MultiEdit).

하네스가 init된 프로젝트에서만, 코드 수정 직후 린트·타입체크(설정 시 테스트)를 돌려
실패하면 결과를 모델 컨텍스트에 넣는다. 차단하지 않는다 (작업 중엔 깨진 게 정상일 수 있다).

v1 대비 변경
  - 결과를 plain stdout이 아니라 additionalContext로 낸다. v1은 PostToolUse의 plain stdout이
    모델에 전달되지 않아 사실상 경고가 보이지 않았다.
  - 설정은 harness.config.json의 "verify" 섹션 (v1의 .claude/verify.json도 읽는다).

verify 섹션 (모두 선택)
  { "lint": "ruff check .", "typecheck": "mypy .", "test": "pytest -q",
    "run_on": ["*.py"], "skip_test_on_edit": true, "timeout": 120 }
"""
import fnmatch
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

HOOK = "verify_guard"


def autodetect(proj):
    has = lambda f: os.path.exists(os.path.join(proj, f))  # noqa: E731
    cfg = {}
    if has("package.json"):
        try:
            with open(os.path.join(proj, "package.json"), encoding="utf-8") as f:
                scripts = (json.load(f) or {}).get("scripts") or {}
        except Exception:
            scripts = {}
        if "typecheck" in scripts:
            cfg["typecheck"] = "npm run -s typecheck"
        elif "type-check" in scripts:
            cfg["typecheck"] = "npm run -s type-check"
        elif has("tsconfig.json"):
            cfg["typecheck"] = "npx --no-install tsc --noEmit"
        if "lint" in scripts:
            cfg["lint"] = "npm run -s lint"
        if "test" in scripts:
            cfg["test"] = "npm test --silent"
        cfg["run_on"] = ["*.ts", "*.tsx", "*.js", "*.jsx", "*.mjs", "*.cjs", "*.vue", "*.svelte"]
    elif has("pyproject.toml") or has("setup.py") or has("requirements.txt"):
        if shutil.which("ruff"):
            cfg["lint"] = "ruff check ."
        if shutil.which("mypy") and (has("mypy.ini") or has("pyproject.toml")):
            cfg["typecheck"] = "mypy ."
        cfg["test"] = "pytest -q"
        cfg["run_on"] = ["*.py"]
    elif has("Cargo.toml"):
        cfg = {"typecheck": "cargo check -q", "test": "cargo test -q", "run_on": ["*.rs"]}
    elif has("go.mod"):
        cfg = {"typecheck": "go vet ./...", "test": "go test ./...", "run_on": ["*.go"]}
    if cfg:
        cfg["skip_test_on_edit"] = True  # 자동감지는 테스트를 편집마다 돌리지 않는다
    return cfg


def run(cmd, cwd, timeout):
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return None, f"시간 초과 ({timeout}s)"
    except Exception as exc:
        return None, f"실행 실패: {exc}"


def main():
    event = _lib.read_event()
    target = _lib.tool_target(event)
    proj = _lib.project_dir(event)
    if not target or not _lib.is_initialized(proj):
        sys.exit(0)
    cfg = _lib.load_config(proj)
    vcfg = dict(cfg.get("verify") or {})
    source = "harness.config.json"
    if vcfg.get("enabled") is False:
        sys.exit(0)
    if not any(vcfg.get(k) for k in ("lint", "typecheck", "test")):
        vcfg, source = autodetect(proj), "자동감지"
    if not vcfg:
        sys.exit(0)

    patterns = vcfg.get("run_on")
    if patterns and not any(fnmatch.fnmatch(os.path.basename(target), p) for p in patterns):
        sys.exit(0)

    order = ["lint", "typecheck", "test"]
    if vcfg.get("skip_test_on_edit", True):
        order.remove("test")
    timeout = int(vcfg.get("timeout", 120))

    problems = []
    for key in order:
        cmd = vcfg.get(key)
        if not cmd:
            continue
        code, output = run(cmd, proj, timeout)
        if code is None:
            problems.append(f"[{key}] {output.strip()[:200]}")
        elif code != 0:
            tail = "\n".join(output.strip().splitlines()[-12:])
            problems.append(f"[{key}] `{cmd}` 실패 (exit {code})\n{tail}")

    if problems:
        text = (f"[verify_guard] 방금 수정 후 검증이 실패했습니다 ({source} 기준). 차단은 하지 않습니다.\n"
                + "\n\n".join(problems)
                + "\n작업 중간이면 이어서 진행해도 되지만, 완료 보고 전에는 반드시 통과시키세요.")
        _lib.audit(proj, HOOK, "warn", target, problems[0][:300])
        _lib.add_context(text, "PostToolUse")
    else:
        _lib.audit(proj, HOOK, "pass", target)
    sys.exit(0)


if __name__ == "__main__":
    main()
