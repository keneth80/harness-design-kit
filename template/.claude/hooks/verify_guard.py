#!/usr/bin/env python3
"""
verify_guard: PostToolUse 훅 (Write|Edit|MultiEdit 대상)
코드 수정 직후 관련 검증(테스트/타입체크/린트)을 실행해 빠른 피드백을 준다.

정책:
  - 검증 명령은 .claude/verify.json 에서 읽는다. 없으면 프로젝트 마커로 자동 감지.
  - 실패해도 차단하지 않는다(exit 0). 경고만 stdout으로 출력.
    (작업 중간엔 테스트가 깨지는 게 정상일 수 있으므로 — TDD red 등)
  - 수정된 파일과 무관한 전체 테스트를 매번 다 돌리면 느리므로, 가능하면
    "빠른" 명령(타입체크/린트)을 우선하고, 테스트는 verify.json에 명시된 경우만.

verify.json 형식 (모두 선택):
  {
    "test":      "pytest -q",
    "typecheck": "mypy .",
    "lint":      "ruff check .",
    "run_on":    ["*.py"],          // 이 패턴의 파일이 수정될 때만 실행 (생략 시 항상)
    "skip_test_on_edit": true       // true면 편집 직후엔 test 생략(느려서), typecheck/lint만
  }

입력: stdin JSON { tool_name, tool_input:{file_path}, cwd, ... }
출력: 항상 exit 0. 검증 결과는 stdout 경고로.
"""
import sys, json, os, subprocess, fnmatch, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from monitor import log_event
except Exception:
    def log_event(*a, **k): pass

def out(msg): print(msg, file=sys.stdout)

def read_event():
    try: return json.loads(sys.stdin.read())
    except Exception: return None

def load_verify_config(cwd):
    p = os.path.join(cwd, ".claude", "verify.json")
    if os.path.exists(p):
        try:
            with open(p) as f: return json.load(f), "verify.json"
        except Exception: pass
    return None, None

def autodetect(cwd):
    """프로젝트 마커로 검증 명령 추측. 빠른 것(타입체크/린트) 위주."""
    cfg = {}
    has = lambda f: os.path.exists(os.path.join(cwd, f))
    # Python
    if has("pyproject.toml") or has("setup.py"):
        if shutil.which("ruff"): cfg["lint"] = "ruff check ."
        if shutil.which("mypy"): cfg["typecheck"] = "mypy ."
        cfg.setdefault("test", "pytest -q")
        cfg["run_on"] = ["*.py"]
    # Node/TS
    elif has("package.json"):
        try:
            with open(os.path.join(cwd,"package.json")) as f: pkg=json.load(f)
            scripts = pkg.get("scripts",{})
            if "typecheck" in scripts: cfg["typecheck"]="npm run typecheck"
            elif has("tsconfig.json") and shutil.which("tsc"): cfg["typecheck"]="tsc --noEmit"
            if "lint" in scripts: cfg["lint"]="npm run lint"
            if "test" in scripts: cfg["test"]="npm test"
        except Exception: pass
        cfg["run_on"]=["*.ts","*.tsx","*.js","*.jsx"]
    # Rust
    elif has("Cargo.toml"):
        cfg["typecheck"]="cargo check"
        cfg["test"]="cargo test"
        cfg["run_on"]=["*.rs"]
    return cfg or None

def run(cmd, cwd):
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                           text=True, timeout=120)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return None, "(검증 시간 초과 120s)"
    except Exception as e:
        return None, f"(검증 실행 실패: {e})"

def main():
    ev = read_event()
    if not ev: sys.exit(0)
    ti = ev.get("tool_input",{}) or {}
    target = ti.get("file_path") or ti.get("path")
    cwd = ev.get("cwd") or os.getcwd()
    if not target: sys.exit(0)

    cfg, src = load_verify_config(cwd)
    if cfg is None:
        cfg = autodetect(cwd); src = "자동감지"
        # 자동감지 시엔 편집 직후 test를 기본 생략한다.
        # (느리고, 도구 미설치/부분구현 단계에서 노이즈가 큼. test는 verify.json에 명시할 때만.)
        if cfg: cfg["skip_test_on_edit"] = True
    if not cfg: sys.exit(0)  # 검증할 게 없음

    # run_on 패턴 필터: 수정 파일이 대상이 아니면 건너뜀
    patterns = cfg.get("run_on")
    if patterns:
        base = os.path.basename(target)
        if not any(fnmatch.fnmatch(base, p) for p in patterns):
            sys.exit(0)

    # 실행 순서: 빠른 것부터 (lint → typecheck → test)
    order = ["lint", "typecheck", "test"]
    if cfg.get("skip_test_on_edit"): order.remove("test")

    problems = []
    for key in order:
        cmd = cfg.get(key)
        if not cmd: continue
        code, output = run(cmd, cwd)
        if code is None:
            problems.append(f"  [{key}] {output.strip()[:200]}")
        elif code != 0:
            tail = "\n".join(output.strip().splitlines()[-8:])  # 마지막 8줄만
            problems.append(f"  [{key}] 실패 (exit {code}):\n{tail}")

    log_event(cwd, "verify_guard", target, "fail" if problems else "pass")
    if problems:
        out(f"[verify_guard][경고] 코드 검증 실패 ({src} 기준). 차단하지 않으나 확인하세요:")
        for p in problems: out(p)
        out("  (작업 중간이면 무시 가능. 완료 전엔 반드시 통과시키세요.)")
    sys.exit(0)

if __name__ == "__main__":
    main()
