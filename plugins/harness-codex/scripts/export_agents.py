#!/usr/bin/env python3
"""export_agents: 도메인 매뉴얼(manual.md) → 각 code_path의 AGENTS.override.md.

Codex CLI는 Claude 하네스(플러그인·스킬·훅)를 읽지 못한다. 그래서 AGENTS.override.md가
Codex에게 주는 유일한 계약서이며, 스스로 완결되어야 한다.

규칙
  - interview_status가 complete가 아니거나 §7 미해결 항목이 있으면 export하지 않는다.
  - 내보내는 내용: §1 책임 범위, §2 핵심 모델, §3 불변 규칙, §4 의존 계약 + 공통 코딩 규칙.
    (§5 근거·§6 함정·§7 미해결은 구현 규칙이 아니므로 넣지 않는다)
  - 위치: code_paths 각 항목에서 glob(*, **) 이전까지의 디렉터리.
  - 메타 블록의 code_paths 목록만 경로로 읽는다 (last_synced 등을 경로로 오인하지 않음).

사용: python3 export_agents.py [--project DIR] [--domain NAME ...] [--dry-run]
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(os.path.dirname(HERE), "skills", "codex-handoff", "references", "coding-rules.md")
SECTION = re.compile(r"^##\s+(\d+)\.\s*(.+?)\s*$", re.M)


def parse_meta(text):
    m = re.search(r"```yaml\n(.*?)```", text, re.S)
    meta = {"code_paths": [], "last_synced": "", "interview_status": ""}
    if not m:
        return meta
    in_paths = False
    for raw in m.group(1).splitlines():
        line = re.sub(r"\s+#.*$", "", raw.strip())  # 줄 끝 주석 제거
        if re.match(r"^code_paths\s*:", line):
            in_paths = True
            inline = line.split(":", 1)[1].strip()
            if inline.startswith("["):
                meta["code_paths"] = [p.strip().strip("'\"") for p in inline.strip("[]").split(",") if p.strip()]
                in_paths = False
            continue
        if in_paths and line.startswith("- "):
            meta["code_paths"].append(line[2:].strip().strip("'\""))
            continue
        if line and not line.startswith("#"):
            in_paths = False
        for key in ("last_synced", "interview_status"):
            if line.startswith(key + ":"):
                meta[key] = line.split(":", 1)[1].strip().strip("'\"")
    return meta


def sections(text):
    out = {}
    marks = list(SECTION.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out[int(m.group(1))] = (m.group(2), text[m.end():end].strip())
    return out


def unresolved(body):
    """§7 본문에 실제 미해결 항목이 있는지 (주석·'없음' 표시는 무시)."""
    cleaned = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    items = [line for line in cleaned.splitlines() if re.match(r"^\s*([-*]|\d+\.|\|)\s*\S", line)]
    items = [line for line in items if not re.search(r"없음|none|n/a|^\s*\|\s*-+", line, re.I)]
    return bool(items)


def target_dir(proj, pattern):
    base = re.split(r"[*?\[]", pattern, maxsplit=1)[0].rstrip("/")
    full = os.path.normpath(os.path.join(proj, base)) if base else proj
    if os.path.splitext(full)[1] and not os.path.isdir(full):
        full = os.path.dirname(full)
    return full


def render(domain, rel_manual, meta, secs, rules):
    def body(n):
        return secs.get(n, ("", "(매뉴얼에 이 섹션이 없습니다)"))[1]
    today = datetime.date.today().isoformat()
    return f"""# AGENTS.override.md — {domain} 도메인

> 이 파일은 `{rel_manual}`에서 자동 생성되었습니다 (harness-codex, {today}).
> 직접 수정하지 마세요. 규칙을 바꾸려면 Claude 쪽에서 인터뷰 → 매뉴얼 → 재export 순서를 거칩니다.
> source: {rel_manual} · synced: {meta.get('last_synced') or '?'} · interview_status: {meta.get('interview_status') or '?'}

이 디렉터리의 코드를 작성·수정할 때 아래 규칙을 **반드시** 따르세요.
규칙은 도메인 설계에서 확정된 것이며, 어기면 다른 도메인과의 계약이 깨집니다.

## 책임 범위
{body(1)}

## 핵심 모델
{body(2)}

## 불변 규칙 (절대 위반 금지)
{body(3)}

## 의존 계약 (방향 엄수)
{body(4)}

## 구현 시 주의
- 위 불변 규칙을 어기는 코드는 작성하지 마세요. 특히 의존 방향과 소유권 규칙을 지키세요.
- 이 규칙에 없는 설계 결정이 필요하면 임의로 정하지 말고 사용자에게 확인을 요청하세요.
- 테스트를 먼저 쓰고(RED) 최소 구현으로 통과시키세요(GREEN). 테스트를 지우거나 건너뛰지 마세요.

{rules.strip()}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    ap.add_argument("--domain", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    proj = os.path.abspath(args.project)
    rules = open(RULES, encoding="utf-8").read() if os.path.exists(RULES) else ""

    manuals = sorted(glob.glob(os.path.join(proj, "docs", "domains", "*", "manual.md")))
    if args.domain:
        manuals = [m for m in manuals if os.path.basename(os.path.dirname(m)) in args.domain]
    if not manuals:
        print("내보낼 매뉴얼이 없습니다 (docs/domains/<domain>/manual.md).")
        return

    report = {"written": [], "skipped": []}
    for manual in manuals:
        domain = os.path.basename(os.path.dirname(manual))
        rel_manual = os.path.relpath(manual, proj)
        text = open(manual, encoding="utf-8").read()
        meta = parse_meta(text)
        secs = sections(text)
        iv = os.path.join(os.path.dirname(manual), "interview.json")
        try:
            status = json.load(open(iv, encoding="utf-8")).get("status")
        except Exception:
            status = meta.get("interview_status")
        if status != "complete":
            report["skipped"].append(f"{domain}: 인터뷰가 complete가 아님 (status={status})")
            continue
        if 7 in secs and unresolved(secs[7][1]):
            report["skipped"].append(f"{domain}: §7 미해결 항목이 있어 보류")
            continue
        if not meta["code_paths"]:
            report["skipped"].append(f"{domain}: 메타 블록에 code_paths가 없음")
            continue
        content = render(domain, rel_manual, meta, secs, rules)
        for pattern in meta["code_paths"]:
            d = target_dir(proj, pattern)
            if os.path.relpath(d, proj).startswith(".."):
                report["skipped"].append(f"{domain}: 프로젝트 밖 경로 {pattern}")
                continue
            out = os.path.join(d, "AGENTS.override.md")
            if not args.dry_run:
                os.makedirs(d, exist_ok=True)
                with open(out, "w", encoding="utf-8") as f:
                    f.write(content)
            report["written"].append(os.path.relpath(out, proj))

    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
