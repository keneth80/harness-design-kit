#!/usr/bin/env python3
"""drift_guard: PreToolUse(Write|Edit|MultiEdit|NotebookEdit).

코드-매뉴얼-인터뷰 3층의 어긋남(drift)을 감시한다. 프로젝트에 docs/domains/가 없으면 아무것도 안 한다.

판정 (대상 파일을 manual.md의 code_paths로 역추적해 도메인을 찾은 뒤)
  - 인터뷰 파일 없음 / status != complete      → 차단 (deny)
  - blocks_completion: true 미해결 질문 존재   → 차단 (deny)
  - 인터뷰가 매뉴얼보다 최신 (Drift A)         → 경고 (모델 컨텍스트 주입)
  - 코드가 매뉴얼 동기화 이후 변경 (Drift B)    → 경고

완화 (harness.config.json)
  "drift_guard": { "mode": "block|warn|off", "warn_paths": ["frontend/**"] }
  warn = 모든 차단을 경고로 강등, warn_paths = 해당 경로만 강등.

v1 대비 변경
  - 차단을 exit 2 대신 permissionDecision=deny JSON으로 낸다 (사유가 모델에 정확히 전달됨).
  - code_paths 접두사 매칭이 경로 경계를 지킨다 (src/auth가 src/authz를 잡던 문제 수정).
"""
import datetime
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

HOOK = "drift_guard"
DOMAINS_DIR = os.path.join("docs", "domains")


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def parse_manual_meta(path):
    """manual.md 머리의 ```yaml 블록에서 last_synced, interview_status, code_paths를 읽는다."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return None
    m = re.search(r"```yaml\n(.*?)```", text, re.S)
    if not m:
        return None
    meta = {"code_paths": [], "last_synced": None, "interview_status": None}
    for line in m.group(1).splitlines():
        line = re.sub(r"\s+#.*$", "", line.strip())  # 줄 끝 주석 제거
        if line.startswith("last_synced:"):
            meta["last_synced"] = line.split(":", 1)[1].strip().strip("'\"")
        elif line.startswith("interview_status:"):
            meta["interview_status"] = line.split(":", 1)[1].strip()
        elif line.startswith("- "):
            meta["code_paths"].append(line[2:].strip().strip("'\""))
    return meta


def path_in(rel, pattern):
    """rel(프로젝트 기준 상대경로)이 code_paths 항목에 속하는지."""
    pattern = pattern.strip()
    while pattern.startswith("./"):
        pattern = pattern[2:]
    if not pattern:
        return False
    if any(c in pattern for c in "*?["):
        return _lib.glob_match(rel, [pattern])
    base = pattern.rstrip("/")
    return rel == base or rel.startswith(base + "/")


def mtime_date(path):
    try:
        return datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()
    except Exception:
        return None


def main():
    event = _lib.read_event()
    target = _lib.tool_target(event)
    if not target:
        sys.exit(0)
    proj = _lib.project_dir(event)
    domains_root = os.path.join(proj, DOMAINS_DIR)
    if not os.path.isdir(domains_root):
        sys.exit(0)

    cfg = _lib.load_config(proj)
    dg = cfg.get("drift_guard") or {}
    mode = dg.get("mode", "block")
    if mode not in ("block", "warn", "off"):
        mode = "block"
    if mode == "off":
        sys.exit(0)

    target_abs = _lib.abspath_in(proj, target)
    rel = _lib.relpath_or_none(target_abs, proj)
    if rel is None:
        sys.exit(0)
    rel = rel.replace("\\", "/")
    if rel.startswith("docs/"):
        sys.exit(0)  # 설계 문서 자체의 수정은 간섭하지 않는다

    matched = []
    for manual in sorted(glob.glob(os.path.join(domains_root, "*", "manual.md"))):
        meta = parse_manual_meta(manual)
        if meta and any(path_in(rel, p) for p in meta["code_paths"]):
            matched.append((os.path.dirname(manual), meta))
    if not matched:
        sys.exit(0)

    warn_paths = dg.get("warn_paths") if isinstance(dg.get("warn_paths"), list) else []
    downgraded = mode == "warn" or _lib.glob_match(rel, warn_paths)
    why = "mode=warn" if mode == "warn" else "warn_paths"

    blocks, warnings = [], []

    def violation(msg):
        if downgraded:
            warnings.append(f"{msg} (완화 모드[{why}]라 차단하지 않음. 구현 후 인터뷰·매뉴얼을 반드시 따라잡으세요.)")
        else:
            blocks.append(msg)

    for domain_dir, meta in matched:
        domain = os.path.basename(domain_dir)
        iv_path = os.path.join(domain_dir, "interview.json")
        interview = read_json(iv_path)
        if interview is None:
            violation(f"'{domain}' 도메인 코드를 고치려 하지만 interview.json이 없습니다. "
                      "domain-interview 스킬로 인터뷰부터 완료하세요.")
            continue
        if interview.get("status") != "complete":
            violation(f"'{domain}' 인터뷰가 아직 complete가 아닙니다(status={interview.get('status')}). "
                      "미확정 상태로 코드를 쓰면 모순이 코드에 굳습니다.")
        blocking = [q for q in interview.get("open_questions", []) if q.get("blocks_completion")]
        if blocking:
            qs = "; ".join(q.get("question", "?") for q in blocking)
            violation(f"'{domain}'에 미해결 필수 결정이 있습니다: {qs}")

        synced = meta.get("last_synced")
        if synced:
            iv_m = mtime_date(iv_path)
            if iv_m and iv_m > synced:
                warnings.append(f"'{domain}': 인터뷰({iv_m})가 매뉴얼(last_synced {synced})보다 최신입니다. "
                                "domain-manual 스킬로 매뉴얼을 갱신하세요.")
            t_m = mtime_date(target_abs)
            if t_m and t_m > synced:
                warnings.append(f"'{domain}': 매뉴얼 동기화 이후 코드가 바뀌었습니다. "
                                "매뉴얼의 불변 규칙을 어기지 않는지 확인하세요.")

    if blocks:
        reason = "[drift_guard] " + " / ".join(blocks)
        _lib.audit(proj, HOOK, "deny", rel, reason)
        _lib.decide("deny", reason)
    if warnings:
        text = "[drift_guard] " + "\n".join(warnings)
        _lib.audit(proj, HOOK, "warn", rel, text)
        _lib.add_context(text, "PreToolUse", user_message=text)
    else:
        _lib.audit(proj, HOOK, "pass", rel)
    sys.exit(0)


if __name__ == "__main__":
    main()
