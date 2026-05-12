#!/usr/bin/env python3
"""Stop Hook (async) — 세션 종료 시 검증 대시보드 HTML 생성"""

import json, os, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

AUDIT_LOG = "/tmp/claude-verifier-audit.jsonl"
OUTPUT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR",".")) / ".claude" / "reports"

def load_entries():
    if not os.path.exists(AUDIT_LOG): return []
    entries = []
    with open(AUDIT_LOG) as f:
        for line in f:
            try: entries.append(json.loads(line.strip()))
            except: pass
    return entries

def analyze(entries):
    s = {"total":len(entries),"passed":0,"blocked":0,"warnings":0,
         "by_hook":Counter(),"blocked_files":[],"issues_by_dim":defaultdict(list)}
    for e in entries:
        r = e.get("result",""); s["by_hook"][e.get("hook","?")] += 1
        if r in ("passed","passed_static_only"): s["passed"] += 1
        elif r == "blocked":
            s["blocked"] += 1
            s["blocked_files"].append({"file":e.get("file",e.get("command","?")),"reason":e.get("reason",""),"ts":e.get("ts","")})
        elif r == "warning": s["warnings"] += 1
        rev = e.get("review")
        if rev:
            for d in ("security","performance","context"):
                dd = rev.get(d,{})
                if dd.get("severity","none") != "none":
                    for i in dd.get("issues",[]):
                        s["issues_by_dim"][d].append({"file":e.get("file",""),"severity":dd["severity"],"issue":i})
    return s

def sev_color(s):
    return {"critical":"#dc2626","high":"#ea580c","medium":"#ca8a04","low":"#2563eb"}.get(s,"#16a34a")

def gen_html(s):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = max(s["total"],1); pr = round(s["passed"]/total*100,1)
    gc = "#16a34a" if pr>=90 else "#ca8a04" if pr>=70 else "#dc2626"
    blocked_rows = "".join(f'<tr><td style="font-family:monospace;font-size:13px">{b["file"][:80]}</td><td>{b["reason"]}</td><td style="font-size:12px;color:#888">{b["ts"][:19]}</td></tr>' for b in s["blocked_files"])
    issues_html = ""
    for dim,items in s["issues_by_dim"].items():
        if not items: continue
        label = {"security":"🔒 보안","performance":"⚡ 성능","context":"📐 맥락"}.get(dim,dim)
        issues_html += f'<h3 style="margin-top:24px">{label}</h3><div style="display:flex;flex-direction:column;gap:6px">'
        for i in items[:20]:
            c = sev_color(i["severity"])
            issues_html += f'<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:#f8fafc;border-left:3px solid {c};border-radius:4px"><span style="background:{c};color:#fff;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:600;text-transform:uppercase">{i["severity"]}</span><span style="font-family:monospace;font-size:12px;color:#64748b">{i["file"][:40]}</span><span style="font-size:13px">{i["issue"]}</span></div>'
        issues_html += "</div>"
    hooks_html = "".join(f'<div class="card" style="flex:1"><div class="label">{h}</div><div class="value">{c}</div></div>' for h,c in s["by_hook"].items())
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><title>Verifier Report</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f172a;color:#e2e8f0;padding:32px;line-height:1.6}}.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:32px;padding-bottom:16px;border-bottom:1px solid #334155}}.header h1{{font-size:24px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px}}.card{{background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155}}.card .label{{font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}}.card .value{{font-size:32px;font-weight:700}}.card .value.green{{color:#4ade80}}.card .value.red{{color:#f87171}}.card .value.yellow{{color:#fbbf24}}.section{{margin-bottom:32px}}.section h2{{font-size:18px;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid #334155}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid #1e293b}}th{{color:#94a3b8;font-size:12px;text-transform:uppercase}}.empty{{color:#64748b;font-style:italic;padding:20px;text-align:center}}</style></head><body>
<div class="header"><h1>🔍 Verifier Report</h1><span style="color:#94a3b8;font-size:13px">{now}</span></div>
<div class="grid"><div class="card"><div class="label">총 검증</div><div class="value">{s['total']}</div></div><div class="card"><div class="label">통과</div><div class="value green">{s['passed']}</div></div><div class="card"><div class="label">차단</div><div class="value red">{s['blocked']}</div></div><div class="card"><div class="label">경고</div><div class="value yellow">{s['warnings']}</div></div></div>
<div class="card" style="margin-bottom:32px"><div style="display:flex;justify-content:space-between"><span class="label">통과율</span><span style="font-size:24px;font-weight:700;color:{gc}">{pr}%</span></div><div style="width:100%;height:8px;background:#334155;border-radius:4px;margin-top:12px;overflow:hidden"><div style="height:100%;width:{pr}%;background:{gc};border-radius:4px"></div></div></div>
<div class="section"><h2>🛑 차단 내역</h2>{'<table><tr><th>파일</th><th>사유</th><th>시각</th></tr>'+blocked_rows+'</table>' if blocked_rows else '<div class="empty">차단 없음 ✅</div>'}</div>
<div class="section"><h2>🤖 AI 이슈</h2>{issues_html or '<div class="empty">이슈 없음 ✅</div>'}</div>
<div class="section"><h2>📊 Hook별 실행</h2><div style="display:flex;gap:16px">{hooks_html or '<div class="empty">-</div>'}</div></div>
</body></html>"""

def main():
    entries = load_entries()
    if not entries: sys.exit(0)
    stats = analyze(entries); html = gen_html(stats)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rp = OUTPUT_DIR / f"verifier_{ts}.html"
    rp.write_text(html, encoding="utf-8")
    latest = OUTPUT_DIR / "latest.html"
    if latest.exists() or latest.is_symlink(): latest.unlink()
    latest.symlink_to(rp.name)
    print(json.dumps({"report":str(rp),"total":stats["total"],"blocked":stats["blocked"]}))
    try: os.rename(AUDIT_LOG, f"{AUDIT_LOG}.{ts}")
    except: pass
    sys.exit(0)

if __name__ == "__main__":
    main()
