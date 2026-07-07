#!/usr/bin/env python3
"""
drift-guard: PreToolUse 훅 (Write|Edit 대상)
코드-매뉴얼-인터뷰 3층의 어긋남(drift)을 감시한다.

판정:
  CHECK_FILE에 적힌 경로의 도메인을 code_paths로 역추적.
  - 그 도메인 인터뷰가 complete 아님       → 차단 (exit 2)
  - blocks_completion: true 미해결 항목 존재 → 차단 (exit 2)
  - 인터뷰가 매뉴얼보다 새로움 (Drift A)     → 경고 (exit 0, stdout)
  - 코드가 매뉴얼보다 새로움 (Drift B)       → 경고 (exit 0, stdout)
  매칭되는 도메인이 없으면 통과(exit 0). 도메인 외 파일은 간섭하지 않는다.

완화 모드 (harness.config.json — 프로젝트 루트, 없으면 기존 동작 그대로 전체 차단):
  {
    "drift_guard": {
      "mode": "block",                 // block(기본) | warn(차단→경고 강등) | off(비활성)
      "warn_paths": ["frontend/**"]    // block 모드여도 이 glob에 걸리면 경고만
    }
  }

입력: stdin JSON { tool_name, tool_input: { file_path | ... }, cwd, ... }
종료: 0=허용, 2=차단(stderr가 Claude에게 피드백됨)
경고 출력: exit 0 + stdout에 훅 JSON. plain stdout은 PreToolUse에서 모델에게 전달되지
않으므로, hookSpecificOutput.additionalContext(모델용)와 systemMessage(사용자용)를 쓴다.
permissionDecision은 넣지 않는다 — "allow"는 권한 시스템을 우회하므로 경고 훅이 쓰면 안 됨.
"""
import sys, json, os, glob, fnmatch, datetime, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from monitor import log_event
except Exception:
    def log_event(*a, **k): pass

DOMAINS_DIR = "docs/domains"
CONFIG_FILE = "harness.config.json"


def emit_warnings(warnings):
    """경고를 훅 JSON으로 출력 — additionalContext는 모델 컨텍스트에 주입된다."""
    text = "\n".join(warnings)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": text,
        },
        "systemMessage": text,
    }, ensure_ascii=False))


_MON = {"cwd": None, "target": None}

def block(msg):
    log_event(_MON["cwd"] or os.getcwd(), "drift_guard", _MON["target"], "blocked")
    print(msg, file=sys.stderr)
    sys.exit(2)


def load_guard_config(cwd):
    """harness.config.json의 drift_guard 섹션. 파일이 없거나 값이 이상하면 기존 동작(block)."""
    cfg = read_json(os.path.join(cwd, CONFIG_FILE))
    dg = (cfg or {}).get("drift_guard") or {}
    mode = dg.get("mode", "block")
    if mode not in ("block", "warn", "off"):
        mode = "block"
    warn_paths = dg.get("warn_paths") or []
    if not isinstance(warn_paths, list):
        warn_paths = []
    return mode, warn_paths


def in_warn_paths(target_abs, cwd, patterns):
    """대상 파일이 warn_paths glob에 걸리는지. 상대경로 기준 fnmatch(‘*’는 ‘/’도 매칭)."""
    try:
        rel = os.path.relpath(target_abs, cwd)
    except ValueError:
        return False
    for pat in patterns:
        pat = pat.strip()
        if not pat:
            continue
        if pat.endswith("/"):
            pat += "**"
        if fnmatch.fnmatch(rel, pat):
            return True
    return False


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def parse_manual_meta(manual_path):
    """manual.md 헤더의 yaml 메타 블록에서 last_synced, code_paths 추출."""
    try:
        with open(manual_path) as f:
            text = f.read()
    except Exception:
        return None
    m = re.search(r"```yaml\n(.*?)```", text, re.S)
    if not m:
        return None
    block_text = m.group(1)
    meta = {"code_paths": [], "last_synced": None, "interview_status": None}
    for line in block_text.splitlines():
        line = line.strip()
        if line.startswith("last_synced:"):
            meta["last_synced"] = line.split(":", 1)[1].strip()
        elif line.startswith("interview_status:"):
            meta["interview_status"] = line.split(":", 1)[1].strip()
        elif line.startswith("- "):  # code_paths 항목
            meta["code_paths"].append(line[2:].strip())
    return meta


def mtime_date(path):
    try:
        return datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()
    except Exception:
        return None


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except Exception:
        sys.exit(0)  # 입력 파싱 실패 시 간섭하지 않음

    tool_input = event.get("tool_input", {}) or {}
    # Write/Edit 계열의 대상 파일 경로 추출 (키 이름이 도구마다 다를 수 있어 관대하게)
    target = (tool_input.get("file_path") or tool_input.get("path")
              or tool_input.get("notebook_path"))
    if not target:
        sys.exit(0)

    cwd = event.get("cwd") or os.getcwd()
    target_abs = os.path.abspath(os.path.join(cwd, target)) if not os.path.isabs(target) else target

    mode, warn_paths = load_guard_config(cwd)
    if mode == "off":
        log_event(cwd, "drift_guard", target, "off")
        sys.exit(0)

    domains_root = os.path.join(cwd, DOMAINS_DIR)
    if not os.path.isdir(domains_root):
        sys.exit(0)  # 이 프로젝트엔 도메인 구조 없음 → 간섭 안 함

    # 각 도메인의 manual.md를 훑어 code_paths로 대상 파일이 어느 도메인인지 역추적
    matched = []
    for manual_path in glob.glob(os.path.join(domains_root, "*", "manual.md")):
        meta = parse_manual_meta(manual_path)
        if not meta:
            continue
        domain_dir = os.path.dirname(manual_path)
        for pat in meta["code_paths"]:
            pat_abs = os.path.abspath(os.path.join(cwd, pat))
            # glob 패턴(**)을 fnmatch로 느슨하게 매칭
            if fnmatch.fnmatch(target_abs, pat_abs) or target_abs.startswith(pat_abs.split("*")[0]):
                matched.append((domain_dir, manual_path, meta))
                break

    _MON["cwd"] = cwd
    _MON["target"] = target
    if not matched:
        sys.exit(0)  # 도메인에 속하지 않는 파일 → 통과

    # 차단 강등 여부: mode=warn 전역 강등, 또는 block 모드라도 warn_paths에 걸리면 강등
    downgraded = (mode == "warn") or in_warn_paths(target_abs, cwd, warn_paths)
    downgrade_reason = "mode=warn" if mode == "warn" else "warn_paths 매칭"

    warnings = []

    def violation(msg):
        """차단 사유 처리: 기본은 block(exit 2), 강등 시 경고로 통과."""
        if downgraded:
            warnings.append(f"{msg} (완화 모드[{downgrade_reason}]로 차단하지 않음 — 반복 구현 후 인터뷰/매뉴얼을 반드시 따라잡으세요)")
        else:
            block(msg)

    for domain_dir, manual_path, meta in matched:
        domain = os.path.basename(domain_dir)
        interview = read_json(os.path.join(domain_dir, "interview.json"))

        # ── 차단 조건 1: 인터뷰 미완성 ──
        if interview is None:
            violation(f"[drift-guard] '{domain}' 도메인 코드를 수정하려 하지만 interview.json이 없습니다. "
                      f"먼저 domain-interview 스킬로 인터뷰를 완료하세요.")
            continue  # 강등 시: 인터뷰 파일이 없으니 이하 판정 불가
        if interview.get("status") != "complete":
            violation(f"[drift-guard] '{domain}' 인터뷰가 아직 complete가 아닙니다(status={interview.get('status')}). "
                      f"구현 전에 인터뷰를 마치세요. 미확정 상태로 코드를 작성하면 모순이 코드에 굳습니다.")

        # ── 차단 조건 2: 미해결 blocking 항목 ──
        blocking = [q for q in interview.get("open_questions", []) if q.get("blocks_completion")]
        if blocking:
            qs = "; ".join(q.get("question", "?") for q in blocking)
            violation(f"[drift-guard] '{domain}'에 미해결 필수 항목이 있습니다: {qs}. "
                      f"이 결정 없이는 구현을 시작할 수 없습니다.")

        # ── 경고 조건 A: 인터뷰가 매뉴얼보다 새로움 ──
        iv_mtime = mtime_date(os.path.join(domain_dir, "interview.json"))
        if meta["last_synced"] and iv_mtime and iv_mtime > meta["last_synced"]:
            warnings.append(f"[drift-guard][경고] '{domain}': 인터뷰가 매뉴얼보다 최신입니다 "
                            f"(interview {iv_mtime} > manual last_synced {meta['last_synced']}). "
                            f"domain-manual 스킬로 매뉴얼을 갱신하세요.")

        # ── 경고 조건 B: 코드가 매뉴얼보다 새로움 (Drift C 후보 → 검토 필요) ──
        if meta["last_synced"]:
            target_mtime = mtime_date(target_abs)
            if target_mtime and target_mtime > meta["last_synced"]:
                warnings.append(f"[drift-guard][검토필요] '{domain}': 코드가 매뉴얼 동기화 시점 이후 변경됩니다. "
                                f"매뉴얼의 불변 규칙을 위반하지 않는지 확인하세요(자동 판정 불가).")

    # 통과(차단 안 됨) 로그
    log_event(cwd, "drift_guard", target, "warn" if warnings else "pass")
    # 경고는 통과시키되 훅 JSON으로 알림 (모델 컨텍스트 + 사용자 표시)
    if warnings:
        emit_warnings(warnings)
    sys.exit(0)


if __name__ == "__main__":
    main()
