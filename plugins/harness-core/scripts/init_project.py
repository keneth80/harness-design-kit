#!/usr/bin/env python3
"""init_project: /harness-core:init 이 호출하는 프로젝트 초기화 스크립트.

v1의 scaffold.sh는 템플릿 폴더를 통째로 복사했다(도구와 데이터가 섞임).
v2는 도구(훅·에이전트·스킬)를 플러그인에 두고, 프로젝트에는 "그 프로젝트의 내용물"만 만든다.

만드는 것 (이미 있으면 건드리지 않음, 단 CLAUDE.md의 하네스 구역은 갱신)
  harness.config.json        하네스 설정 (이 파일이 있으면 워크플로우 훅이 켜진다)
  CLAUDE.md                  <!-- harness:begin --> ~ <!-- harness:end --> 구역 삽입/갱신
  CONTEXT.md                 도메인 용어 사전
  docs/adr/                  의사결정 기록
  docs/lessons-learned.md    학습된 교훈 (~/.claude/harness-lessons.md가 있으면 그걸 시작점으로)
  docs/error-log.md          오류 기록
  .gitignore                 .env 계열이 빠져 있으면 추가

v1에서 옮겨오는 것
  .claude/verify.json        → harness.config.json의 verify로 병합 (원본은 남겨둠)
  harness.config.json(v1)    → profile 필드 제거, version 2로 갱신

사용: python3 init_project.py [--project DIR] [--dry-run] [--json]
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(os.path.dirname(HERE), "templates")
BEGIN = "<!-- harness:begin"
END = "<!-- harness:end -->"
GITIGNORE_LINES = [".env", ".env.local", ".env.*.local", ".env.production"]
V1_HOOKS = ["security_gate.py", "drift_guard.py", "secret_scan.py", "verify_guard.py",
            "codemap.py", "codemap_session.py", "codemap_refresh.py", "backpressure.py",
            "code_reviewer.py", "report_generator.py", "monitor.py", "monitor_report.py"]


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text, actions, dry, label):
    actions.append(label)
    if dry:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def merge_config(proj, actions, dry):
    path = os.path.join(proj, "harness.config.json")
    template = json.loads(read(os.path.join(TEMPLATES, "harness.config.json")))
    existing = None
    if os.path.exists(path):
        try:
            existing = json.loads(read(path))
        except Exception:
            actions.append("harness.config.json: JSON이 깨져 있어 건드리지 않음 (직접 확인 필요)")
            return
    cfg = dict(template)
    if existing:
        for key, val in existing.items():
            if isinstance(val, dict) and isinstance(cfg.get(key), dict):
                cfg[key] = {**cfg[key], **val}
            else:
                cfg[key] = val
        cfg.pop("profile", None)
        cfg["version"] = 2
    legacy_verify = os.path.join(proj, ".claude", "verify.json")
    if not cfg.get("verify") and os.path.exists(legacy_verify):
        try:
            cfg["verify"] = json.loads(read(legacy_verify))
            actions.append(".claude/verify.json 내용을 harness.config.json의 verify로 옮김")
        except Exception:
            pass
    new_text = json.dumps(cfg, ensure_ascii=False, indent=2) + "\n"
    if existing is None:
        write(path, new_text, actions, dry, "harness.config.json 생성")
    elif new_text != read(path):
        write(path, new_text, actions, dry, "harness.config.json을 v2 형식으로 갱신")


def upsert_claude_md(proj, actions, dry):
    path = os.path.join(proj, "CLAUDE.md")
    section = read(os.path.join(TEMPLATES, "claude-md-section.md")).strip() + "\n"
    if not os.path.exists(path):
        name = os.path.basename(os.path.abspath(proj))
        write(path, f"# {name}\n\n{section}", actions, dry, "CLAUDE.md 생성 (하네스 구역 포함)")
        return
    text = read(path)
    if BEGIN in text and END in text:
        start = text.index(BEGIN)
        end = text.index(END) + len(END)
        new = text[:start] + section.strip() + text[end:]
        if new != text:
            write(path, new, actions, dry, "CLAUDE.md 하네스 구역 갱신")
    else:
        write(path, text.rstrip() + "\n\n" + section, actions, dry, "CLAUDE.md에 하네스 구역 추가")


def ensure_file(proj, rel, src, actions, dry):
    dst = os.path.join(proj, rel)
    if os.path.exists(dst):
        return
    write(dst, read(src), actions, dry, f"{rel} 생성")


def ensure_gitignore(proj, actions, dry):
    if not os.path.isdir(os.path.join(proj, ".git")):
        return
    path = os.path.join(proj, ".gitignore")
    text = read(path) if os.path.exists(path) else ""
    present = {line.strip() for line in text.splitlines()}
    missing = [line for line in GITIGNORE_LINES if line not in present]
    if missing:
        block = ("\n" if text and not text.endswith("\n") else "") + \
                "\n# 시크릿 (harness-core가 추가)\n" + "\n".join(missing) + "\n"
        write(path, text + block, actions, dry, ".gitignore에 " + ", ".join(missing) + " 추가")


def legacy_report(proj):
    notes = []
    hooks_dir = os.path.join(proj, ".claude", "hooks")
    found = [h for h in V1_HOOKS if os.path.exists(os.path.join(hooks_dir, h))]
    if found:
        notes.append(f"v1 훅 스크립트 {len(found)}개가 .claude/hooks/에 남아 있습니다. "
                     "플러그인과 이중으로 돌지 않게 .claude/settings.json의 hooks 항목을 지우고 "
                     "스크립트를 정리하세요 (/harness-core:init 스킬의 v1 정리 절차).")
    for leftover in (".claude/profiles", ".claudeignore"):
        if os.path.exists(os.path.join(proj, leftover)):
            if leftover == ".claudeignore":
                notes.append(".claudeignore는 Claude Code가 읽지 않는 파일입니다. 시크릿 차단은 file_gate가 맡으니 "
                             "지워도 됩니다.")
            else:
                notes.append(".claude/profiles/(lite/full 전환)는 v2에서 플러그인 켜고 끄기로 바뀌었습니다.")
    settings = os.path.join(proj, ".claude", "settings.json")
    if os.path.exists(settings):
        try:
            hooks = (json.loads(read(settings)) or {}).get("hooks") or {}
            flat = json.dumps(hooks)
            if re.search(r"\.claude/hooks/(security_gate|drift_guard|verify_guard|secret_scan)", flat):
                notes.append(".claude/settings.json에 v1 훅 등록이 남아 있습니다.")
        except Exception:
            pass
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    proj = os.path.abspath(args.project)
    if not os.path.isdir(proj):
        print(f"프로젝트 디렉터리가 없습니다: {proj}", file=sys.stderr)
        sys.exit(1)

    actions = []
    merge_config(proj, actions, args.dry_run)
    upsert_claude_md(proj, actions, args.dry_run)
    ensure_file(proj, "CONTEXT.md", os.path.join(TEMPLATES, "CONTEXT.md"), actions, args.dry_run)
    shared = os.path.join(os.path.expanduser("~"), ".claude", "harness-lessons.md")
    lessons_src = shared if os.path.exists(shared) else os.path.join(TEMPLATES, "docs", "lessons-learned.md")
    ensure_file(proj, "docs/lessons-learned.md", lessons_src, actions, args.dry_run)
    ensure_file(proj, "docs/error-log.md", os.path.join(TEMPLATES, "docs", "error-log.md"), actions, args.dry_run)
    adr = os.path.join(proj, "docs", "adr")
    if not os.path.isdir(adr):
        actions.append("docs/adr/ 생성")
        if not args.dry_run:
            os.makedirs(adr, exist_ok=True)
            open(os.path.join(adr, ".gitkeep"), "w").close()
    ensure_gitignore(proj, actions, args.dry_run)
    notes = legacy_report(proj)

    if args.json:
        print(json.dumps({"project": proj, "dry_run": args.dry_run, "actions": actions, "notes": notes},
                         ensure_ascii=False, indent=2))
        return
    print(f"하네스 초기화{' (미리보기)' if args.dry_run else ''}: {proj}")
    for a in actions or ["바꿀 것이 없습니다 (이미 최신)"]:
        print(f"  - {a}")
    for n in notes:
        print(f"  ! {n}")


if __name__ == "__main__":
    main()
