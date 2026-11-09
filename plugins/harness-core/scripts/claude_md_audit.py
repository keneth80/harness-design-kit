#!/usr/bin/env python3
"""claude_md_audit: CLAUDE.md를 규칙 묶음으로 나누고 어디로 옮기면 좋을지 1차 분류한다 (바꾸지 않음).

CLAUDE.md는 매 대화의 맨 앞에 통째로 실린다. 가방에 한 달에 한 번 쓰는 물건까지 다 넣고 다니는 셈이라,
늘 쓰는 것만 남기고 나머지는 제자리(훅·설정, 스킬, 문서)로 보낸다.

분류 (규칙 기반 추정. 최종 판단은 /harness-core:slim에서 사람과 함께 한다):
  keep       모든 작업에 늘 필요한 짧은 규칙
  enforce    어기면 안 되는 금지 규칙 → 훅·하네스 설정·권한 deny로 강제 (이미 하네스가 막는 것은 covered)
  skill      특정 작업의 절차 (단계, 명령, 코드 블록) → 프로젝트 스킬
  reference  표, 링크, 긴 목록 같은 참고 자료 → docs로 옮기고 한 줄 링크

  python3 claude_md_audit.py [--project DIR]
"""
import argparse
import json
import os
import re

FILES = ("CLAUDE.md", os.path.join(".claude", "CLAUDE.md"), "CLAUDE.local.md")
BEGIN, END = "<!-- harness:begin", "<!-- harness:end -->"

PROHIBIT = re.compile(r"절대|금지|하지\s*마|하지\s*않는다|말\s*것|never|must not|do not|don't|forbidden|not allowed", re.I)
# 하네스가 이미 기계적으로 막는 것: 이런 규칙은 CLAUDE.md에서 빼도 된다
COVERED = [
    (re.compile(r"\.env|시크릿|secret|비밀\s*키|api\s*key|토큰|token|credential|자격\s*증명", re.I), "시크릿 읽기·쓰기 (file_gate, bash_gate)"),
    (re.compile(r"rm\s+-rf|강제\s*푸시|force[\s-]*push|reset\s+--hard|drop\s+table", re.I), "위험한 명령 (bash_gate)"),
    (re.compile(r"테스트.{0,12}(skip|건너|지우|삭제|약하)|skip.{0,10}test|골든|golden|스냅샷", re.I), "테스트 약화 (시험지 보호)"),
    (re.compile(r"curl\s*\|\s*(ba)?sh|외부\s*(업로드|전송)|upload", re.I), "외부 전송 (bash_gate)"),
    (re.compile(r"주민(등록)?번호|카드\s*번호|개인\s*정보", re.I), "개인정보 쓰기 (file_gate)"),
]
ENFORCE_TARGET = re.compile(r"운영|prod|production|배포|deploy|migration|마이그레이션|main\s*브랜치|main branch|"
                            r"package|패키지\s*설치|lock|잠금|설정\s*파일|config", re.I)
PROCEDURE = re.compile(r"절차|단계|순서|방법|how to|steps?|배포|릴리스|release|마이그레이션|migrat|셋업|setup|"
                       r"할\s*때|when you|실행한다|run ", re.I)


def blocks_of(text):
    """제목(#) 단위로 나누고, 하네스 관리 구역은 따로 센다."""
    out, cur, in_harness, harness_lines = [], None, False, 0
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith(BEGIN):
            in_harness = True
        if in_harness:
            harness_lines += 1
            if line.startswith(END):
                in_harness = False
            continue
        if re.match(r"^#{1,6}\s", line) or cur is None:
            cur = {"start": i, "end": i, "heading": line.lstrip("#").strip() if line.startswith("#") else "(머리말)", "lines": []}
            out.append(cur)
        cur["lines"].append(line)
        cur["end"] = i
    return [b for b in out if any(x.strip() for x in b["lines"])], harness_lines


def classify(block):
    body = "\n".join(block["lines"])
    content = [x for x in block["lines"] if x.strip() and not x.startswith("#")]
    n = len(content)
    numbered = sum(1 for x in content if re.match(r"^\s*\d+[.)]\s", x))
    fences = body.count("```") // 2
    table_rows = sum(1 for x in content if x.strip().startswith("|"))
    links = len(re.findall(r"https?://|\]\(", body))
    covered = sorted({why for rx, why in COVERED if rx.search(body)})
    if PROHIBIT.search(body) and covered and n <= 8:
        return "enforce", "covered", "하네스가 이미 막음: " + ", ".join(covered)
    if PROHIBIT.search(body) and (covered or ENFORCE_TARGET.search(body)) and n <= 8:
        return "enforce", "", "금지 규칙. 훅·하네스 설정·권한 deny로 강제할 수 있음"
    if numbered >= 3 or fences >= 1 or (PROCEDURE.search(block["heading"]) and n >= 4):
        return "skill", "", f"특정 작업 절차 (번호 단계 {numbered}, 코드 블록 {fences})"
    if table_rows >= 4 or links >= 3 or n >= 15:
        return "reference", "", f"참고 자료 (표 {table_rows}줄, 링크 {links}, {n}줄)"
    return "keep", "", "짧은 공통 규칙"


def audit(proj):
    files, blocks = [], []
    for rel in FILES:
        path = os.path.join(proj, rel)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        bl, harness_lines = blocks_of(text)
        files.append({"path": rel, "lines": len(text.splitlines()), "harness_section_lines": harness_lines})
        for b in bl:
            guess, sub, reason = classify(b)
            excerpt = " ".join(x.strip() for x in b["lines"] if x.strip() and not x.startswith("#"))[:160]
            blocks.append({"file": rel, "start": b["start"], "end": b["end"], "heading": b["heading"][:80],
                           "lines": b["end"] - b["start"] + 1, "guess": guess, "covered": sub == "covered",
                           "reason": reason, "excerpt": excerpt})
    totals = {}
    for b in blocks:
        totals[b["guess"]] = totals.get(b["guess"], 0) + b["lines"]
    total = sum(f["lines"] for f in files)
    keep = totals.get("keep", 0) + sum(f["harness_section_lines"] for f in files)
    return {"files": files, "total_lines": total, "lines_by_guess": totals,
            "estimated_after": keep, "limit": 200, "blocks": blocks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    args = ap.parse_args()
    print(json.dumps(audit(os.path.abspath(args.project)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
