#!/usr/bin/env python3
"""slop_scan: 화면 코드와 글에 묻은 AI 티(안티 슬롭)를 찾는다.

훅 (`slop_scan.py --hook`, init한 프로젝트에서만, harness.config.json의 slop.mode에 따라)
  - warn (기본): PostToolUse에서 방금 추가한 줄만 검사해 걸린 줄과 고칠 방향을 모델에게 알린다. 막지 않는다.
  - ask: PreToolUse에서 쓰기 전에 검사해 걸리면 사용자 확인을 받는다.
  - off: 아무것도 하지 않는다.
  slop.judge가 stop이면 Stop에서도 돈다: 이번 요청에서 바뀐 화면·글 파일이 아직 심사 전이면 응답 종료를 한 번 막고
  slop-judge 에이전트(만든 쪽과 분리된 읽기 전용 심사자)에게 맡기게 한다. 같은 파일은 한 요청 안에서 judge_rounds번까지만.
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
JUDGE_FILE = "slop-judged.json"


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


def _file_hash(path):
    try:
        with open(path, "rb") as f:
            return _lib.short_hash(f.read().decode("utf-8", "replace"))
    except OSError:
        return ""


def _load_state():
    path = os.path.join(_lib.data_dir(), JUDGE_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        return path, state if isinstance(state, dict) else {}
    except Exception:
        return path, {}


def _save_state(path, state, proj, mine):
    state.pop(proj, None)
    state[proj] = mine
    while len(state) > 50:
        state.pop(next(iter(state)))
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        return True
    except OSError:
        return False


def mark_judged(event, proj, scfg):
    """Claude가 스스로 slop-judge를 불렀으면(PostToolUse Agent) 지금 내용을 심사한 것으로 적어 Stop에서 다시 막지 않는다."""
    ti = event.get("tool_input") or {}
    if not str(ti.get("subagent_type") or "").endswith("slop-judge"):
        return
    path, state = _load_state()
    mine = state.get(proj) or {}
    for rel in _lib.slop_changed_paths(proj, scfg):
        rec = mine.get(rel) or {}
        mine[rel] = {"hash": _file_hash(os.path.join(proj, rel)), "n": int(rec.get("n") or 0) + 1}
    _save_state(path, state, proj, mine)


def judge_at_stop(event, proj, scfg):
    """바뀐 화면·글 파일 중 심사 전이거나 심사 뒤 다시 바뀐 것이 있으면 Stop을 막고 심사를 맡긴다.

    상태는 프로젝트별 {경로: {hash, n}}. n은 한 요청 안의 심사 횟수라서, 사용자의 새 요청에서 처음 맞는
    Stop(stop_hook_active가 false)이면 0으로 돌린다. 내용이 그대로인 파일(hash 같음)은 다시 보지 않는다.
    """
    paths = _lib.slop_changed_paths(proj, scfg)
    if not paths:
        return
    state_path, state = _load_state()
    mine = state.get(proj) or {}
    fresh_turn = not event.get("stop_hook_active")
    rounds = max(int(scfg.get("judge_rounds") or 2), 1)
    due, skipped = [], []
    for rel in paths:
        h = _file_hash(os.path.join(proj, rel))
        rec = mine.get(rel) or {}
        n = 0 if fresh_turn else int(rec.get("n") or 0)
        if rec.get("hash") == h:
            continue
        if n >= rounds:
            skipped.append(rel)
            continue
        due.append((rel, h, n))
    if not due:
        return
    limit = max(int(scfg.get("judge_max_files") or 8), 1)
    picked, rest = due[:limit], due[limit:]
    for rel, h, n in picked:
        mine[rel] = {"hash": h, "n": n + 1}
    for rel in list(mine):
        if rel not in paths:
            mine.pop(rel)  # 커밋됐거나 지운 파일은 잊는다
    if not _save_state(state_path, state, proj, mine):
        return  # 기록을 못 남기면 같은 심사를 반복할 수 있으니 막지 않는다
    files = "\n".join(f"- {rel}" for rel, _, _ in picked)
    more = f"\n(이번에 넘기지 않은 파일 {len(rest)}개는 다음 종료 때 심사합니다)" if rest else ""
    _lib.audit(proj, HOOK, "block", picked[0][0], f"judge {len(picked)} files")
    _lib.block_stop(
        "[slop_judge] 이번에 바뀐 화면·글 파일이 AI 심사 전입니다. 끝내기 전에 Agent 도구로 `harness-core:slop-judge` 에이전트를"
        " 불러 아래 파일을 심사받으세요. 프롬프트에 파일 목록과, 사용자가 요청에서 직접 지정한 표현이 있으면 그 표현을 함께 적습니다.\n"
        + files + more
        + "\n결과의 '고칠 것'은 고치고, 의도한 표현이면 그대로 두고 이유를 한 줄 남긴 뒤 끝내세요. 사용자가 직접 지정한 표현은 바꾸지 말고 보고만 합니다. "
          "에이전트를 부를 수 없는 환경이면 /harness-core:anti-slop 기준으로 직접 점검하고 끝내세요.")


def hook():
    event = _lib.read_event()
    proj = _lib.project_dir(event)
    if not _lib.is_initialized(proj):
        return
    scfg = _lib.slop_config(_lib.load_config(proj))
    if event.get("hook_event_name") == "Stop":
        if scfg.get("judge") == "stop":
            judge_at_stop(event, proj, scfg)
        return
    if event.get("tool_name") in ("Agent", "Task"):
        if scfg.get("judge") == "stop" and event.get("hook_event_name") == "PostToolUse":
            mark_judged(event, proj, scfg)
        return
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
