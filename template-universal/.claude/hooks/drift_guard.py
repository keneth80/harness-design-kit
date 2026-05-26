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

입력: stdin JSON { tool_name, tool_input: { file_path | ... }, cwd, ... }
종료: 0=허용, 2=차단(stderr가 Claude에게 피드백됨)
"""
import sys, json, os, glob, fnmatch, datetime, re

DOMAINS_DIR = "docs/domains"


def log(msg):
    print(msg, file=sys.stdout)


def block(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


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

    if not matched:
        sys.exit(0)  # 도메인에 속하지 않는 파일 → 통과

    warnings = []
    for domain_dir, manual_path, meta in matched:
        domain = os.path.basename(domain_dir)
        interview = read_json(os.path.join(domain_dir, "interview.json"))

        # ── 차단 조건 1: 인터뷰 미완성 ──
        if interview is None:
            block(f"[drift-guard] '{domain}' 도메인 코드를 수정하려 하지만 interview.json이 없습니다. "
                  f"먼저 domain-interview 스킬로 인터뷰를 완료하세요.")
        if interview.get("status") != "complete":
            block(f"[drift-guard] '{domain}' 인터뷰가 아직 complete가 아닙니다(status={interview.get('status')}). "
                  f"구현 전에 인터뷰를 마치세요. 미확정 상태로 코드를 작성하면 모순이 코드에 굳습니다.")

        # ── 차단 조건 2: 미해결 blocking 항목 ──
        blocking = [q for q in interview.get("open_questions", []) if q.get("blocks_completion")]
        if blocking:
            qs = "; ".join(q.get("question", "?") for q in blocking)
            block(f"[drift-guard] '{domain}'에 미해결 필수 항목이 있습니다: {qs}. "
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

    # 경고는 통과시키되 stdout으로 알림
    for w in warnings:
        log(w)
    sys.exit(0)


if __name__ == "__main__":
    main()
