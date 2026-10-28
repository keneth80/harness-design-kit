#!/usr/bin/env python3
"""design_guard: PostToolUse(Write|Edit|MultiEdit) — harness-design.

디자인 토큰을 정한 프로젝트에서, 화면 코드에 색상·간격·폰트 크기를 직접 박는 것을 잡아 모델에게 알린다.
막지는 않는다 (디자인은 반복하면서 잡히는 경우가 많다). 경고는 additionalContext로 들어간다.

켜지는 조건: harness.config.json에 "design": {"tokens": [...]}가 있을 때만 (/harness-design:design-system이 만든다).
끄기: "design": {"guard": "off"}

잡는 것
  - 색상 리터럴: #abc, #aabbcc(aa), rgb()/rgba()/hsl()/hsla()/oklch()  (토큰 파일과 SVG는 제외)
  - Tailwind 임의값: bg-[#123456], text-[13px], p-[7px], w-[312px] 등 대괄호 안의 리터럴
  - 인라인 스타일의 px 값: style={{ padding: 12 }}, style="margin: 13px" 중 토큰 배수(4px)가 아닌 값
허용하는 것
  - 0, 1px(헤어라인), 100%, transparent, currentColor, var(--…), theme(…)
  - "design": {"allow": ["#000", "12px"]}에 적은 값
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

HOOK = "design_guard"
UI_EXT = (".css", ".scss", ".sass", ".less", ".tsx", ".jsx", ".ts", ".js", ".vue", ".svelte", ".html", ".astro")
SKIP_PARTS = ("node_modules/", "/dist/", "/build/", ".next/", "/coverage/", "/__snapshots__/")
SKIP_NAMES = re.compile(r"(\.test\.|\.spec\.|\.stories\.|tailwind\.config|theme\.|tokens?\.)", re.I)

# 뒤에 하이픈·글자·여는 중괄호가 오면 색이 아니라 ID 선택자나 앵커(#add-btn, #bed {, #faq)로 본다
COLOR = re.compile(r"(?<![\w&-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-]|\s*\{)"
                   r"|\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\(\s*[\d.]+")
TW_ARBITRARY = re.compile(r"\b[a-z][\w-]*-\[(#[0-9a-fA-F]{3,8}|\d+(?:\.\d+)?(?:px|rem|em)|rgba?\([^\]]*\))\]")
INLINE_PX = re.compile(r"(?:padding|margin|gap|top|left|right|bottom|width|height|fontSize|font-size|"
                       r"borderRadius|border-radius|lineHeight|line-height)\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)(px)?\b")
GRID = 4


def candidate_lines(text):
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "/*", "*", "<!--")):
            continue
        if "var(--" in line and not COLOR.search(line.replace("var(--", "")):
            continue
        yield n, line


def scan(text, allow):
    findings = []
    for n, line in candidate_lines(text):
        for m in TW_ARBITRARY.finditer(line):
            if m.group(1) not in allow:
                findings.append(f"{n}행 Tailwind 임의값 `{m.group(0)}`")
        line_wo_tw = TW_ARBITRARY.sub("", line)
        for m in COLOR.finditer(line_wo_tw):
            lit = m.group(0)
            if lit not in allow and lit.lower() not in allow:
                findings.append(f"{n}행 색상 리터럴 `{lit}`")
        for m in INLINE_PX.finditer(line_wo_tw):
            val = float(m.group(1))
            raw = m.group(1) + (m.group(2) or "")
            if val in (0, 1) or raw in allow:
                continue
            if val % GRID != 0:
                findings.append(f"{n}행 간격·크기 `{m.group(0).strip()}` (4px 격자 밖)")
    return findings


def main():
    event = _lib.read_event()
    target = _lib.tool_target(event)
    proj = _lib.project_dir(event)
    if not target or not target.endswith(UI_EXT):
        sys.exit(0)
    cfg = _lib.load_config(proj)
    design = cfg.get("design") or {}
    tokens = design.get("tokens") or []
    if not tokens or design.get("guard", "warn") == "off":
        sys.exit(0)

    rel = _lib.relpath_or_none(_lib.abspath_in(proj, target), proj) or target
    rel = rel.replace("\\", "/")
    if any(p in "/" + rel for p in SKIP_PARTS) or SKIP_NAMES.search(os.path.basename(rel)):
        sys.exit(0)
    if _lib.glob_match(rel, tokens) or _lib.glob_match(rel, design.get("ignore") or []):
        sys.exit(0)

    text = _lib.written_text(event)
    allow = set(design.get("allow") or [])
    findings = scan(text, allow)
    if not findings:
        _lib.audit(proj, HOOK, "pass", rel)
        sys.exit(0)

    shown = findings[:8]
    more = f" 외 {len(findings) - 8}건" if len(findings) > 8 else ""
    msg = (f"[design_guard] {rel}에 디자인 토큰을 쓰지 않은 값이 있습니다 (차단하지 않음):\n- "
           + "\n- ".join(shown) + more
           + f"\n토큰 파일({', '.join(tokens)})의 변수나 테마 키로 바꾸세요. 새 값이 정말 필요하면 "
             "토큰을 먼저 추가하고 그 토큰을 쓰세요. 의도한 예외면 harness.config.json의 design.allow에 적습니다.")
    _lib.audit(proj, HOOK, "warn", rel, shown[0])
    _lib.add_context(msg, "PostToolUse")
    sys.exit(0)


if __name__ == "__main__":
    main()
