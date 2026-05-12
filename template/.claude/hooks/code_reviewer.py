#!/usr/bin/env python3
"""PostToolUse Hook — 정적 분석 + AI 코드 검증 (보안/성능/맥락)"""

import json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier-scripts"))
from llm_client import ask_json, is_available

AUDIT_LOG = "/tmp/claude-verifier-audit.jsonl"

REVIEW_SYSTEM = """\
You are a code reviewer. Analyze the code change and respond in JSON only.
{
  "security":    {"severity":"none|low|medium|high|critical","issues":[]},
  "performance": {"severity":"none|low|medium|high|critical","issues":[]},
  "context":     {"severity":"none|low|medium|high|critical","issues":[]},
  "summary":"one line","should_block":false
}
Set should_block=true ONLY for critical/high security (secrets, injection, RCE)."""

SKIP_PATTERNS = [".lock","package-lock","yarn.lock",".min.js",".min.css",".map",
    ".d.ts","node_modules/",".git/",".png",".jpg",".svg",".ico",".woff",".ttf"]

SECRET_PATTERNS = [
    (r'(?:api[_-]?key|apikey)\s*[=:]\s*["\'][A-Za-z0-9]{16,}', "하드코딩 API키"),
    (r'(?:password|passwd|pwd)\s*[=:]\s*["\'][^"\']{4,}', "하드코딩 비밀번호"),
    (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', "Private key"),
    (r'sk-[A-Za-z0-9]{20,}', "OpenAI API키"), (r'ghp_[A-Za-z0-9]{36}', "GitHub PAT"),
]

def log_event(fp, result, review=None, reason=""):
    try:
        entry = {"ts":datetime.now(timezone.utc).isoformat(),"hook":"code_reviewer",
                 "file":fp,"result":result,"reason":reason}
        if review: entry["review"] = review
        with open(AUDIT_LOG,"a") as f: f.write(json.dumps(entry,ensure_ascii=False)+"\n")
    except: pass

def extract(data):
    ti = data.get("tool_input",{})
    tn = data.get("tool_name","")
    fp = ti.get("file_path","") or ti.get("path","") or ti.get("filePath","")
    parts = []
    if tn == "Write":
        parts.append(f"[NEW] {fp}\n{ti.get('content',ti.get('file_text',''))}")
    elif tn in ("Edit","MultiEdit"):
        old,new = ti.get("old_str",""),ti.get("new_str","")
        if old or new: parts.append(f"[EDIT] {fp}\n- {old}\n+ {new}")
        for e in ti.get("edits",[]):
            parts.append(f"[EDIT] {fp}\n- {e.get('old_str','')}\n+ {e.get('new_str','')}")
    code = "\n".join(parts)
    return fp, code[:3000]+"...(truncated)" if len(code)>3000 else code

def static_check(code):
    issues = []
    for p,d in SECRET_PATTERNS:
        if re.search(p,code,re.I): issues.append(f"🔴 CRITICAL: {d}")
    if re.search(r'\beval\s*\(',code): issues.append("⚠️ eval() 사용")
    if re.search(r"f[\"'].*(?:SELECT|INSERT|UPDATE|DELETE).*\{",code):
        issues.append("⚠️ f-string SQL (injection 위험)")
    return issues

def main():
    try: data = json.loads(sys.stdin.read())
    except: sys.exit(0)

    fp, code = extract(data)
    if not code or any(p in fp for p in SKIP_PATTERNS): sys.exit(0)

    # Phase 1: 정적 분석
    static = static_check(code)
    critical = [i for i in static if "CRITICAL" in i]
    if critical:
        log_event(fp,"blocked",reason="; ".join(critical))
        print(f"🛑 정적 차단\n파일: {fp}\n"+"\n".join(critical), file=sys.stderr)
        sys.exit(2)

    # Phase 2: AI 검증
    review = None
    if is_available():
        review = ask_json(f"Review this code change:\n\n{code}", system=REVIEW_SYSTEM)

    if review:
        if review.get("should_block"):
            log_event(fp,"blocked",review=review)
            issues = []
            for d in ("security","performance","context"):
                for i in review.get(d,{}).get("issues",[]): issues.append(f"  [{d}] {i}")
            print(f"🛑 AI 차단\n파일: {fp}\n{review.get('summary','')}\n"+"\n".join(issues),file=sys.stderr)
            sys.exit(2)
        log_event(fp,"passed",review=review)
        # 성공은 침묵 — 컨텍스트에 아무것도 추가하지 않음
    else:
        log_event(fp,"passed_static_only" if not static else "warning",reason="; ".join(static))

    sys.exit(0)

if __name__ == "__main__":
    main()
