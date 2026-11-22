#!/usr/bin/env python3
"""doc_budget: 에이전트가 보는 문서의 크기를 잰다. 경량화는 AI가 한다 (/harness-core:slim → doc-slimmer 에이전트).

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
  python3 doc_budget.py            크기 보고 (--json)
"""
import argparse
import json
import os
import re
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


def main(argv):
    ap = argparse.ArgumentParser(description="에이전트가 보는 문서 크기 점검")
    ap.add_argument("--project", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    proj = os.path.abspath(args.project or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())

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
