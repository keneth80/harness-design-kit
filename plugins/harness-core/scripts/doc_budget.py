#!/usr/bin/env python3
"""doc_budget: 에이전트가 보는 문서의 크기를 재고, 큰 문서를 색인과 보관으로 나누는 것을 돕는다.

책상 위 서류철과 같다. 매일 펼치는 표지(색인)와 지금 유효한 것만 책상에 두고, 지난 서류는 서랍(보관 파일)에 넣는다.
버리지 않고 옮긴다.

두 종류로 잰다.
  매번 실리는 문서  CLAUDE.md, .claude/CLAUDE.md, CLAUDE.local.md, 그 안의 @import, .claude/rules/*.md(paths 조건 없는 것).
                   대화마다 통째로 실리므로 합계로 본다.
  자주 읽는 문서    DECISIONS.md, ADR, CONTEXT.md, AGENTS.md, spec·prd, lessons-learned, error-log, progress 등.
                   에이전트가 작업 때마다 통째로 읽기 쉬워서 파일마다 본다.
토큰 수는 글자 수로 어림한 값이다 (영문 4자에 1, 한글 등은 1자에 1). 정확한 사용량은 Claude Code의 /context.

harness.config.json
  "docs": {"notice": true, "always_lines": 200, "always_tokens": 5000,
           "read_lines": 400, "read_tokens": 10000, "read_paths": [...], "ignore_paths": [...]}

CLI
  python3 doc_budget.py                       크기 보고 (--json)
  python3 doc_budget.py --entries FILE        항목(제목 단위) 목록: 번호, 제목, 줄 수, 상태 추정, 날짜 (--level 2면 ## 단위)
  python3 doc_budget.py --archive FILE --pick 3,5-7 --to docs/archive/decisions-2026.md
                                              고른 항목을 글자 하나 바꾸지 않고 보관 파일로 옮기고,
                                              원본에는 제목 한 줄과 보관 위치만 남긴다 (--no-stub이면 안 남김).
                                              옮기기 전에 원본을 .harness/slim-backup/에 복사한다.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

DEFAULTS = {
    "notice": True,
    "always_lines": 200,      # Claude Code 문서가 권하는 CLAUDE.md 상한
    "always_tokens": 5000,
    "read_lines": 400,
    "read_tokens": 10000,
    "read_paths": ["DECISIONS.md", "docs/DECISIONS.md", "docs/decisions*.md", "docs/decisions/**/*.md",
                   "decisions/**/*.md", "docs/adr/**/*.md", "adr/**/*.md", "CONTEXT.md", "AGENTS.md",
                   "docs/spec*.md", "docs/prd*.md", "docs/ui-spec.md", "docs/test-cases.md", "docs/goal.md",
                   "docs/lessons-learned.md", "docs/error-log.md", "PROGRESS.md", "docs/progress*.md",
                   "docs/design/brief.md", "docs/domains/**/*.md"],
    "ignore_paths": ["docs/archive/**", "archive/**", "*archive*.md", "node_modules/**", ".harness/**"],
}
ALWAYS = ("CLAUDE.md", os.path.join(".claude", "CLAUDE.md"), "CLAUDE.local.md")
SKIP = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next", "coverage",
        "target", "out", ".turbo", ".cache", "vendor", "Pods", ".harness"}
IMPORT_RE = re.compile(r"(?<![\w`/])@((?:\.{1,2}/|[\w-][\w.-]*/)*[\w.-]+\.(?:md|mdx|txt))\b")
STATUS_RE = re.compile(r"superseded|deprecated|obsolete|rejected|replaced|reverted|resolved|done|"
                       r"폐기|대체|번복|철회|무효|기각|취소|완료|해결", re.I)
STUB_MARK = "→ 보관:"  # 보관한 항목 자리에 남기는 제목 꼬리. 이 제목은 이미 옮긴 항목이다
INDEX_RE = re.compile(r"^(색인|목차|index|contents|table of contents)\b", re.I)  # 색인 절은 항목이 아니다
DATE_RE = re.compile(r"(20\d\d)[-./](\d{1,2})[-./](\d{1,2})")


def config(cfg):
    return _lib._merge(DEFAULTS, (cfg or {}).get("docs") or {})


def tokens(text):
    ascii_n = sum(1 for ch in text if ord(ch) < 128)
    return int(ascii_n / 4 + (len(text) - ascii_n))


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _rel(proj, path):
    return os.path.relpath(path, proj).replace("\\", "/")


def _strip_code(text):
    text = re.sub(r"```.*?```|~~~.*?~~~", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def _rule_is_conditional(text):
    m = re.match(r"---\s*\n(.*?)\n---", text, re.S)
    return bool(m and re.search(r"^paths\s*:", m.group(1), re.M))


def always_docs(proj):
    """매 대화에 실리는 문서 [(rel, text)]. @import는 들여온 파일 기준 상대 경로로 5단계까지 따라간다."""
    out, seen = [], set()

    def add(path, depth):
        real = os.path.realpath(path)
        if real in seen or depth > 5:
            return
        text = _read(path)
        if text is None:
            return
        rel = _rel(proj, path)
        if rel.startswith(".."):
            return  # 프로젝트 밖(사용자 전역 등)은 이 프로젝트의 예산에 넣지 않는다
        seen.add(real)
        out.append((rel, text))
        for m in IMPORT_RE.finditer(_strip_code(text)):
            add(os.path.join(os.path.dirname(path), m.group(1)), depth + 1)

    for rel in ALWAYS:
        add(os.path.join(proj, rel), 0)
    rules = os.path.join(proj, ".claude", "rules")
    for dp, _, fns in sorted(os.walk(rules)) if os.path.isdir(rules) else []:
        for fn in sorted(fns):
            if fn.endswith(".md"):
                path = os.path.join(dp, fn)
                text = _read(path)
                if text is not None and not _rule_is_conditional(text):
                    add(path, 0)
    return out


def read_docs(proj, dcfg, exclude=(), budget=1.0):
    out, start = [], time.time()
    for dp, dns, fns in os.walk(proj):
        dns[:] = sorted(d for d in dns if d not in SKIP and not (d.startswith(".") and d != ".claude"))
        for fn in sorted(fns):
            if not fn.endswith((".md", ".mdx", ".txt")):
                continue
            rel = _rel(proj, os.path.join(dp, fn))
            if rel in exclude or _lib.glob_match(rel, dcfg.get("ignore_paths")):
                continue
            if _lib.glob_match(rel, dcfg.get("read_paths")):
                text = _read(os.path.join(dp, fn))
                if text is not None:
                    out.append((rel, text))
        if time.time() - start > budget:
            break
    return out


def kind_of(rel):
    low = rel.lower()
    if re.search(r"decision|adr", low):
        return "decisions"
    if re.search(r"lessons|error-log|progress", low):
        return "log"
    if low.endswith("context.md"):
        return "glossary"
    if re.search(r"spec|prd|test-cases|domains/|goal|brief", low):
        return "spec"
    return "other"


def report(proj, cfg=None, initialized=None):
    cfg = cfg if cfg is not None else _lib.load_config(proj)
    dcfg = config(cfg)
    if initialized is None:
        initialized = _lib.is_initialized(proj)
    always = [{"file": rel, "lines": len(t.splitlines()), "tokens": tokens(t)} for rel, t in always_docs(proj)]
    total = {"lines": sum(d["lines"] for d in always), "tokens": sum(d["tokens"] for d in always)}
    always_over = total["lines"] > int(dcfg["always_lines"]) or total["tokens"] > int(dcfg["always_tokens"])
    read = []
    if initialized:  # 자주 읽는 문서 목록은 하네스 문서 관례라서 init한 프로젝트에서만 본다
        for rel, t in read_docs(proj, dcfg, exclude={d["file"] for d in always}):
            n, tk = len(t.splitlines()), tokens(t)
            read.append({"file": rel, "lines": n, "tokens": tk, "kind": kind_of(rel),
                         "over": n > int(dcfg["read_lines"]) or tk > int(dcfg["read_tokens"])})
    return {"always": always, "always_total": total, "always_over": always_over,
            "always_limit": {"lines": int(dcfg["always_lines"]), "tokens": int(dcfg["always_tokens"])},
            "read": read, "read_limit": {"lines": int(dcfg["read_lines"]), "tokens": int(dcfg["read_tokens"])}}


def _tk(n):
    return f"약 {round(n, -2):,}토큰" if n >= 1000 else f"약 {n}토큰"


def notice(proj):
    """세션 시작 때 한 번 알린다. 크기가 바뀌었을 때만 다시 알린다 (매 세션 반복하지 않음)."""
    try:
        cfg = _lib.load_config(proj)
        if not config(cfg).get("notice", True):
            return []
        rep = report(proj, cfg)
    except Exception:
        return []
    msgs, sig = [], []
    if rep["always_over"]:
        files = ", ".join(f"{d['file']} {d['lines']}줄" for d in rep["always"])
        tot, lim = rep["always_total"], rep["always_limit"]
        msgs.append(f"harness: 매 대화에 실리는 문서가 깁니다 ({files}, 합계 {tot['lines']}줄 {_tk(tot['tokens'])}). "
                    f"길수록 맥락을 차지하고 규칙을 덜 지킵니다 (권장 {lim['lines']}줄·{_tk(lim['tokens'])} 이하). "
                    "/harness-core:slim으로 강제할 규칙은 훅·설정으로, 절차는 스킬로 나눌 수 있습니다.")
        sig.append("A:" + ",".join(f"{d['file']}:{d['lines']}" for d in rep["always"]))
    big = [d for d in rep["read"] if d["over"]]
    if big:
        files = ", ".join(f"{d['file']} {d['lines']}줄 {_tk(d['tokens'])}" for d in big[:5])
        more = f" 외 {len(big) - 5}개" if len(big) > 5 else ""
        msgs.append(f"harness: 에이전트가 자주 읽는 문서가 큽니다 ({files}{more}). 통째로 읽을 때마다 맥락을 씁니다. "
                    f"/harness-core:slim {big[0]['file']} 로 지금 유효한 것만 색인에 남기고 지난 항목은 보관 파일로 옮길 수 있습니다.")
        sig.append("R:" + ",".join(f"{d['file']}:{d['lines']}" for d in big))
    if not msgs:
        return []
    mark = os.path.join(_lib.data_dir(), "doc_budget_notice.json")
    seen = _lib._read_json(mark) or {}
    key, value = os.path.abspath(proj), "|".join(sig)
    if seen.get(key) == value:
        return []
    seen[key] = value
    try:
        os.makedirs(os.path.dirname(mark), exist_ok=True)
        with open(mark, "w", encoding="utf-8") as f:
            json.dump(seen, f)
    except OSError:
        pass
    return msgs


# ── 항목 나누기와 보관 ───────────────────────────────────────────────

def pick_level(heads):
    """항목 경계로 쓸 제목 단계. 결정·교훈 같은 항목은 제목이 저마다 다르고, 그 안의 소제목(배경·결정·결과)은
    같은 이름이 되풀이된다. 그래서 제목이 3개 이상이고 80% 이상 서로 다른 가장 얕은 단계를 고른다.
    없으면 2개 이상인 가장 얕은 단계."""
    by = {lv: [t for _, l, t in heads if l == lv] for lv in range(2, 7)}
    for lv in range(2, 7):
        ts = by[lv]
        if len(ts) >= 3 and len(set(ts)) >= 0.8 * len(ts):
            return lv
    return next((lv for lv in range(2, 7) if len(by[lv]) >= 2), None)


def entries(text, level=None):
    """제목 단위 항목. 경계 단계는 pick_level이 고르고, level(2~6)로 정할 수도 있다.
    코드 블록 안의 #은 제목이 아니다. 반환: (머리말 줄 수, [{n, title, start, end, lines, status, date}]), 줄 번호는 0부터."""
    lines = text.splitlines(keepends=True)
    heads, fence = [], False
    for i, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        m = re.match(r"(#{2,6})\s+(.*\S)", line)
        if m and not fence:
            heads.append((i, len(m.group(1)), m.group(2).strip()))
    level = level or pick_level(heads)
    if level is None or not any(lv == level for _, lv, _ in heads):
        return len(lines), []
    starts = [(i, t) for i, lv, t in heads if lv == level and not INDEX_RE.match(t)]
    if not starts:
        return len(lines), []
    # 항목 단계보다 얕은 제목(예: 항목이 ###일 때의 ##)과 색인 절은 항목을 끊는다. 색인은 번호를 받지 않아서
    # 색인을 넣기 전과 뒤의 항목 번호가 같다
    cuts = sorted([i for i, lv, t in heads if lv < level or (lv == level and INDEX_RE.match(t))] + [len(lines)])
    out = []
    for k, (i, title) in enumerate(starts):
        nxt = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        end = min([c for c in cuts if c > i] + [nxt])
        body = "".join(lines[i:end])
        d = DATE_RE.search(body)
        st = STATUS_RE.search(title) or STATUS_RE.search("".join(lines[i:min(end, i + 6)]))
        status = "보관됨" if STUB_MARK in title else (st.group(0) if st else "")
        out.append({"n": k + 1, "title": title, "start": i, "end": end, "lines": end - i,
                    "status": status, "date": "-".join(d.groups()) if d else ""})
    return starts[0][0], out


def _pick(spec, count):
    got = set()
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            got.update(range(int(a), int(b) + 1))
        else:
            got.add(int(part))
    bad = [n for n in got if n < 1 or n > count]
    if bad:
        raise ValueError(f"없는 항목 번호: {sorted(bad)} (1~{count})")
    return sorted(got)


def archive(proj, src_rel, pick, dest_rel, stub=True, level=None):
    src = _lib.abspath_in(proj, src_rel)
    dest = _lib.abspath_in(proj, dest_rel)
    root = os.path.realpath(proj)
    inside = lambda p: bool(p) and os.path.realpath(p).startswith(root + os.sep)  # noqa: E731
    if not inside(src) or not inside(dest) or not os.path.isfile(src):
        raise ValueError("원본이나 보관 경로가 프로젝트 밖이거나 없습니다")
    if os.path.realpath(src) == os.path.realpath(dest):
        raise ValueError("원본과 보관 파일이 같습니다")
    with open(src, encoding="utf-8") as f:
        text = f.read()
    _, items = entries(text, level)
    nums = _pick(pick, len(items))
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    chosen = [it for it in items if it["n"] in nums and it["status"] != "보관됨"]
    if not chosen:
        raise ValueError("옮길 항목이 없습니다 (이미 보관한 항목만 골랐습니다)")
    moved = "".join("".join(lines[it["start"]:it["end"]]) for it in chosen)

    # 되돌리기용 백업
    backup_dir = os.path.join(proj, ".harness", "slim-backup")
    os.makedirs(backup_dir, exist_ok=True)
    gi = os.path.join(proj, ".harness", ".gitignore")
    if not os.path.exists(gi):
        with open(gi, "w", encoding="utf-8") as f:
            f.write("*\n")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(backup_dir, f"{os.path.basename(src)}.bak-{stamp}")
    shutil.copy2(src, backup)

    src_name = _rel(proj, src)
    dest_name = _rel(proj, dest)
    link = os.path.relpath(dest, os.path.dirname(src)).replace("\\", "/")
    new_lines, pos = [], 0
    for it in chosen:
        new_lines += lines[pos:it["start"]]
        if stub:
            head = lines[it["start"]].rstrip("\n")
            new_lines.append(f"{head} {STUB_MARK} [{dest_name}]({link})\n\n")
        pos = it["end"]
    new_lines += lines[pos:]

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    existed = os.path.exists(dest)
    with open(dest, "a", encoding="utf-8") as f:
        if not existed:
            f.write(f"# 보관: {os.path.basename(src)}\n\n원본은 `{src_name}`. 지금은 유효하지 않거나 오래된 항목을 옮겨 둔 곳입니다. "
                    "필요할 때만 찾아 읽습니다.\n\n")
        f.write(moved if moved.endswith("\n") else moved + "\n")
    with open(src, "w", encoding="utf-8") as f:
        f.write("".join(new_lines))

    # 옮긴 글이 보관 파일에 그대로 있는지 확인한다
    if moved not in (_read(dest) or ""):
        shutil.copy2(backup, src)
        raise RuntimeError("보관 파일 확인에 실패해서 원본을 되돌렸습니다")
    return {"moved": [it["title"] for it in chosen], "file": src_name, "archive": dest_name,
            "lines_before": len(lines), "lines_after": len("".join(new_lines).splitlines()),
            "backup": _rel(proj, backup), "stub": stub}


def main(argv):
    ap = argparse.ArgumentParser(description="에이전트가 보는 문서 크기 점검과 보관")
    ap.add_argument("--project", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--entries", metavar="FILE")
    ap.add_argument("--archive", metavar="FILE")
    ap.add_argument("--pick", default="")
    ap.add_argument("--to", default="")
    ap.add_argument("--no-stub", action="store_true")
    ap.add_argument("--level", type=int, choices=range(2, 7), help="항목 경계 제목 단계 (2면 ##). 기본은 자동")
    args = ap.parse_args(argv)
    proj = os.path.abspath(args.project or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())

    if args.archive:
        if not args.pick or not args.to:
            print("--archive에는 --pick과 --to가 필요합니다", file=sys.stderr)
            return 2
        try:
            res = archive(proj, args.archive, args.pick, args.to, stub=not args.no_stub, level=args.level)
        except (ValueError, RuntimeError, OSError) as exc:
            print(f"보관하지 못했습니다: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(res, ensure_ascii=False, indent=None if args.json else 2))
        return 0

    if args.entries:
        path = _lib.abspath_in(proj, args.entries)
        inside = path and os.path.realpath(path).startswith(os.path.realpath(proj) + os.sep)
        text = _read(path) if inside else None
        if text is None:
            print(f"읽을 수 없습니다: {args.entries}", file=sys.stderr)
            return 1
        head, items = entries(text, args.level)
        lv = len(text.splitlines()[items[0]["start"]].split()[0]) if items else 0
        out = {"level": lv, "file": _rel(proj, path), "lines": len(text.splitlines()), "tokens": tokens(text),
               "kind": kind_of(_rel(proj, path)), "preamble_lines": head,
               "entries": [dict({k: v for k, v in it.items() if k not in ("start", "end")}, line=it["start"] + 1)
                           for it in items]}
        if args.json:
            print(json.dumps(out, ensure_ascii=False))
        else:
            print(f"{out['file']}: {out['lines']}줄 {_tk(out['tokens'])}, 항목 {len(items)}개 (항목 단위 {'#' * lv or '없음'}, 머리말 {head}줄). "
                  "단위가 틀리면 --level로 정한다")
            for it in out["entries"]:
                extra = " · ".join(x for x in (it["status"], it["date"]) if x)
                print(f"{it['n']:>4}. L{it['line']:<5} {it['lines']:>4}줄  {it['title'][:60]}" + (f"  [{extra}]" if extra else ""))
        return 0

    rep = report(proj)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False))
        return 0
    tot, lim = rep["always_total"], rep["always_limit"]
    print(f"매 대화에 실리는 문서: 합계 {tot['lines']}줄 {_tk(tot['tokens'])} (기준 {lim['lines']}줄·{_tk(lim['tokens'])})"
          + ("  ← 초과" if rep["always_over"] else ""))
    for d in rep["always"]:
        print(f"  {d['file']}: {d['lines']}줄 {_tk(d['tokens'])}")
    rl = rep["read_limit"]
    print(f"자주 읽는 문서 (파일당 기준 {rl['lines']}줄·{_tk(rl['tokens'])}):" if rep["read"] else "자주 읽는 문서: 없음")
    for d in sorted(rep["read"], key=lambda d: -d["tokens"]):
        print(f"  {d['file']}: {d['lines']}줄 {_tk(d['tokens'])} [{d['kind']}]" + ("  ← 초과" if d["over"] else ""))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:  # `| head`로 잘라 읽을 때
        sys.stderr.close()
        sys.exit(0)
