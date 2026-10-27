#!/usr/bin/env python3
"""backpressure: Stop (harness-full).

응답을 끝내기 전에 린트·타입체크·테스트를 모두 돌리고, 실패하면 종료를 막고 고치게 한다.
성공하면 아무것도 출력하지 않는다 (컨텍스트를 오염시키지 않음).

v1 대비 변경
  - init된 프로젝트에서만, 그리고 마지막 통과 이후 작업 트리가 바뀌었을 때만 돈다
    (질문만 주고받은 턴에서 테스트를 다시 돌리지 않는다).
  - 무한 루프 방지: 같은 세션에서 연속 3번 막았는데도 실패하면 종료를 허용하고 사용자에게 알린다.
  - 검증 명령은 core의 verify 설정(harness.config.json)을 그대로 쓴다.
  - 끄기: harness.config.json의 "backpressure": {"enabled": false}
"""
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

HOOK = "backpressure"
MAX_BLOCKS = 3


def tree_fingerprint(proj):
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=proj, capture_output=True,
                              text=True, timeout=10).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=proj,
                                capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None
    digest = hashlib.sha1()
    digest.update(head.encode())
    for line in sorted(status.splitlines()):
        path = line[3:].split(" -> ")[-1]
        digest.update(line.encode("utf-8", "replace"))
        try:
            digest.update(str(os.path.getmtime(os.path.join(proj, path))).encode())
        except OSError:
            pass
    return digest.hexdigest()


def checks_for(proj, cfg):
    vcfg = dict(cfg.get("verify") or {})
    if not any(vcfg.get(k) for k in ("lint", "typecheck", "test")):
        vcfg = autodetect(proj)
    return [(k, vcfg[k]) for k in ("lint", "typecheck", "test") if vcfg.get(k)], int(vcfg.get("timeout", 180))


def autodetect(proj):
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


def state_path(session_id):
    return os.path.join(_lib.data_dir(), "backpressure", f"{session_id or 'nosession'}.json")


def load_state(session_id):
    try:
        with open(state_path(session_id), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(session_id, state):
    path = state_path(session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)


def main():
    event = _lib.read_event()
    proj = _lib.project_dir(event)
    if not _lib.is_initialized(proj):
        sys.exit(0)
    cfg = _lib.load_config(proj)
    if not (cfg.get("backpressure") or {}).get("enabled", True):
        sys.exit(0)

    session = event.get("session_id") or ""
    state = load_state(session)
    fp = tree_fingerprint(proj)
    if fp and state.get("passed_fp") == fp:
        sys.exit(0)  # 마지막 통과 이후 바뀐 게 없음

    checks, timeout = checks_for(proj, cfg)
    if not checks:
        sys.exit(0)

    failures = []
    for key, cmd in checks:
        try:
            r = subprocess.run(cmd, shell=True, cwd=proj, capture_output=True, text=True, timeout=timeout)
            if r.returncode != 0:
                out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
                failures.append(f"[{key}] `{cmd}` 실패 (exit {r.returncode})\n" + "\n".join(out[-40:]))
        except subprocess.TimeoutExpired:
            failures.append(f"[{key}] `{cmd}` 시간 초과 ({timeout}s)")

    if not failures:
        # 검사가 만든 산출물(캐시·리포트)까지 포함한 상태를 기억해야 다음 턴에 헛돌지 않는다
        save_state(session, {"passed_fp": tree_fingerprint(proj), "blocks": 0})
        _lib.audit(proj, HOOK, "pass", proj)
        sys.exit(0)

    blocks = int(state.get("blocks", 0)) + 1 if event.get("stop_hook_active") else 1
    if blocks > MAX_BLOCKS:
        save_state(session, {"blocks": 0})
        msg = (f"백프레셔가 {MAX_BLOCKS}번 연속 재작업을 요구했지만 검증이 계속 실패합니다. "
               "자동 재시도를 멈추고 종료를 허용합니다. 남은 실패를 사용자에게 보고하세요.")
        _lib.audit(proj, HOOK, "error", proj, msg)
        print(json.dumps({"systemMessage": "harness backpressure: " + msg}, ensure_ascii=False))
        sys.exit(0)

    save_state(session, {"blocks": blocks})
    reason = ("[backpressure] 끝내기 전에 아래 검증을 통과시켜야 합니다 "
              f"(시도 {blocks}/{MAX_BLOCKS}). 테스트를 지우거나 건너뛰지 말고 원인을 고치세요.\n\n"
              + "\n\n".join(failures))
    _lib.audit(proj, HOOK, "block", proj, failures[0][:300])
    _lib.block_stop(reason)


if __name__ == "__main__":
    main()
