#!/usr/bin/env python3
"""slop_scan: 화면 코드와 글에 묻은 AI 티(안티 슬롭)를 찾는다.

훅 (`slop_scan.py --hook`, init한 프로젝트에서만, harness.config.json의 slop.mode에 따라)
  - warn (기본): PostToolUse에서 방금 추가한 줄만 검사해 걸린 줄과 고칠 방향을 모델에게 알린다. 막지 않는다.
  - ask: PreToolUse에서 쓰기 전에 검사해 걸리면 사용자 확인을 받는다.
  - off: 아무것도 하지 않는다.
  같은 세션에서 같은 줄은 한 번만 알린다. 검사 자체가 실패하면 조용히 넘어간다 (보안 게이트가 아니다).

CLI
  python3 slop_scan.py                 커밋 기준(slop.base, 기본 HEAD)에서 바뀐 줄과 새 파일 검사
  python3 slop_scan.py --base main     다른 기준과 비교
  python3 slop_scan.py --files a.tsx   이 파일들 전체 검사
  python3 slop_scan.py --rules         규칙 목록
  종료 코드: 0 = 없음, 1 = 찾음
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

HOOK = "slop_scan"
SEEN_FILE = "slop-seen.json"


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def _edit_pairs(ti):
    if isinstance(ti.get("edits"), list):
        return [(e.get("old_string") or "", e.get("new_string") or "", bool(e.get("replace_all")))
                for e in ti["edits"] if isinstance(e, dict)]
    return [(ti.get("old_string") or "", ti.get("new_string") or "", bool(ti.get("replace_all")))]


def changes(event, full):
    """(바꾸기 전 글, 바꾼 뒤 글). Pre에서는 디스크가 이전 상태, Post에서는 새 상태다."""
    ti = event.get("tool_input") or {}
    name = event.get("tool_name") or ""
    pre = event.get("hook_event_name") == "PreToolUse"
    disk = _read(full)
    if name == "Write":
        new = ti.get("content") or ""
        if pre:
            return disk or "", new
        resp = event.get("tool_response") or {}
        old = resp.get("originalFile") if isinstance(resp, dict) else None
        return old or "", disk if disk is not None else new
    pairs = _edit_pairs(ti)
    if pre:
        new = disk or ""
        for old_s, new_s, every in pairs:
            new = new.replace(old_s, new_s) if every else new.replace(old_s, new_s, 1)
        return disk or "", new
    # Post: 편집한 조각끼리 비교하고 줄 번호는 새 파일에서 찾는다
    return "\n".join(o for o, _, _ in pairs), "\n".join(n for _, n, _ in pairs)


def locate(added, all_lines):
    """조각에서 찾은 추가 줄에 새 파일의 줄 번호를 붙인다."""
    used, out = set(), []
    for _, line in added:
        n = next((i for i, l in enumerate(all_lines, 1) if l == line and i not in used), 0)
        if n:
            used.add(n)
        out.append((n, line))
    return out


def unseen(found, session, proj):
    """같은 세션에서 이미 알린 줄은 뺀다. 파일 하나에 세션 20개까지만 기억한다."""
    if not session:
        return found
    path = os.path.join(_lib.data_dir(), SEEN_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            seen = json.load(f)
        if not isinstance(seen, dict):
            seen = {}
    except Exception:
        seen = {}
    mine = seen.get(session) or []
    keys = [_lib.short_hash(f"{proj}|{f['file']}|{f['rule']}|{f['text']}") for f in found]
    fresh = [f for f, k in zip(found, keys) if k not in mine]
    seen.pop(session, None)
    seen[session] = (mine + [k for k in keys if k not in mine])[-2000:]
    while len(seen) > 20:
        seen.pop(next(iter(seen)))
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(seen, f)
    except OSError:
        pass
    return fresh


def hook():
    event = _lib.read_event()
    proj = _lib.project_dir(event)
    if not _lib.is_initialized(proj):
        return
    scfg = _lib.slop_config(_lib.load_config(proj))
    mode = scfg.get("mode") or "warn"
    pre = event.get("hook_event_name") == "PreToolUse"
    if mode == "off" or (pre and mode != "ask") or (not pre and mode != "warn"):
        return
    full = _lib.abspath_in(proj, _lib.tool_target(event))
    rel = _lib.relpath_or_none(full, proj) if full else None
    if not rel or not _lib.slop_kinds(rel, scfg):
        return
    old, new = changes(event, full)
    added = _lib.slop_added(old, new)
    if not added:
        return
    if pre:
        all_lines = new.splitlines()
    else:
        all_lines = (_read(full) or new).splitlines()
        if event.get("tool_name") != "Write":
            added = locate(added, all_lines)
    found = _lib.slop_scan_lines(rel, added, scfg, all_lines)
    if pre:
        if found:
            _lib.audit(proj, HOOK, "ask", rel, found[0]["rule"])
            _lib.decide("ask", "[harness] AI 티가 나는 줄이 있습니다. 그대로 쓸지 확인하세요.\n" + _lib.slop_format(found, 6),
                        user_message=f"harness: {rel}에 AI 티 {len(found)}건")
        return
    found = unseen(found, event.get("session_id"), proj)
    if not found:
        return
    _lib.audit(proj, HOOK, "warn", rel, found[0]["rule"])
    _lib.add_context(
        "[slop_scan] 방금 쓴 줄에 AI 기본값 티가 있습니다. 막지는 않습니다.\n"
        + _lib.slop_format(found)
        + "\n이 주제에서만 나올 구체적인 선택(실제 사실, 브랜드 색, 정한 서체)으로 바꾸세요. 의도한 것이면 그대로 두고 "
          "이유를 짧게 말하세요. 계속 예외로 둘 표현이면 사용자에게 slop.allow 추가를 제안하세요 (설정 파일은 직접 고치지 않는다). "
          "한 줄만 예외면 그 줄에 slop-ok 주석을 답니다.",
        "PostToolUse")


def cli(argv):
    ap = argparse.ArgumentParser(description="AI 티 검사")
    ap.add_argument("--project", default="")
    ap.add_argument("--base", default="")
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--rules", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    proj = os.path.abspath(args.project or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    cfg = _lib.load_config(proj)
    scfg = _lib.slop_config(cfg)
    if args.rules:
        for rid, kind, _, msg in _lib._slop_rules(scfg):
            print(f"{rid:20} {kind:4} {msg}")
        return 0
    if args.files is not None:
        found = []
        for path in args.files:
            full = _lib.abspath_in(proj, path)
            rel = _lib.relpath_or_none(full, proj) or path
            lines = (_read(full) or "").splitlines()
            found += _lib.slop_scan_lines(rel, list(enumerate(lines, 1)), scfg, lines)
    else:
        found = _lib.slop_scan_tree(proj, cfg, args.base or None)
    if args.json:
        print(json.dumps({"passed": not found, "findings": found}, ensure_ascii=False))
    else:
        print(_lib.slop_format(found, 50) if found else "AI 티 없음")
    return 1 if found else 0


if __name__ == "__main__":
    if "--hook" not in sys.argv:
        sys.exit(cli(sys.argv[1:]))
    try:
        hook()
    except Exception as exc:  # 조언용 훅이라 실패해도 작업을 막지 않는다
        try:
            # 게이트 오류 알림(error)에 섞이지 않게 warn으로 남긴다 (HARNESS_MONITOR=1일 때 기록)
            _lib.audit(os.getcwd(), HOOK, "warn", "", "검사 오류: " + repr(exc))
        except Exception:
            pass
    sys.exit(0)
