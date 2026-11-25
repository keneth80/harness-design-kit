#!/usr/bin/env python3
"""review_gate: 끝내기 전 독립 검토 게이트.

요리사가 접시를 내기 전에 따로 간을 보는 사람을 거치게 한다. 실험(같은 과제 3번씩)에서 하네스를 설치만 한 구현은
그냥 구현과 차이가 없었고, 끝내기 전에 분리된 검토 에이전트를 거친 구현만 품질 점수가 크게 올랐다
(블라인드 리뷰 31점 → 41점, 50점 만점). 그래서 검토를 명령이 아니라 기본 흐름으로 만든다.

init한 프로젝트에서만, harness.config.json의 review.mode가 stop(기본)일 때
  Stop              이번 요청에서 바뀐 코드가 min_lines 이상이고 아직 검토 전이면 종료를 한 번 막고
                    code-verifier(항상)와 security-reviewer(인증·권한·SQL 등 민감한 변경일 때)를 부르게 한다.
                    테스트 원장이 fail이면 막지 않는다 (테스트부터 고칠 차례).
  PostToolUse Agent 검토 에이전트를 부르면 그때의 내용을 검토한 것으로 적는다. 백그라운드로 돌기 시작한 검토
                    (run_in_background, 또는 오래 걸려 Claude Code가 비동기로 돌린 것)는 "결과 대기"로 적어 두고,
                    결과가 올 때까지 종료를 막지 않는다 (결과 알림이 새 턴을 열어 반영하게 된다).
  UserPromptSubmit  사용자의 새 요청이면 검토 횟수를 0으로 돌린다. Stop 훅 피드백과, 결과 대기 중에 들어온
                    백그라운드 결과 알림은 새 요청으로 치지 않는다 (실제 세션에서 둘 다 이 이벤트로 들어왔고,
                    횟수가 초기화되며 검토가 3번 반복됐다).
같은 내용은 다시 검토시키지 않고, 한 요청 안에서 검토(스스로 부른 것 포함)와 요구를 rounds번까지만 한다.
실패해도 작업을 막지 않는다 (fail-open).
"""
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

HOOK = "review_gate"
STATE_DIR = "review-gate"
CODE_AGENT = "harness-core:code-verifier"
SEC_AGENT = "harness-core:security-reviewer"

DEFAULTS = {
    "mode": "stop",          # stop | off
    "min_lines": 40,         # 바뀐 코드 줄 수(추가+삭제, 테스트·문서 제외)가 이보다 적으면 건너뜀
    "rounds": 1,             # 한 요청 안에서 검토를 요구하는 최대 횟수. 2면 고친 뒤 재검토까지
    "security": "auto",      # auto: 민감한 변경일 때만 | always | never
    "security_model": "sonnet",  # 보안 검토 모델. 깊은 검토(thorough)만 opus
    "quick": True,           # 빠른 검토: 보고서 파일 없이 고칠 것 최대 5개를 20줄 안으로
    "static": True,          # 에이전트 전에 결정적 정적 검사(ruff 보안·버그 규칙)를 먼저 돌려 결과를 넘김
    "code_paths": ["*.py", "*.js", "*.mjs", "*.cjs", "*.ts", "*.tsx", "*.jsx", "*.go", "*.rs", "*.java", "*.kt",
                   "*.rb", "*.php", "*.cs", "*.swift", "*.vue", "*.svelte", "*.sql", "*.prisma"],
    "ignore_paths": ["node_modules/**", "dist/**", "build/**", ".next/**", "vendor/**", "coverage/**",
                     ".harness/**", "_workspace/**", "docs/**", "*.min.*", "*.lock", "*.d.ts"],
    "security_paths": ["*auth*", "*login*", "*session*", "*permission*", "*acl*", "*polic*", "*role*",
                       "*payment*", "*billing*", "*admin*", "*middleware*", "*security*", "*token*",
                       "*.sql", "*migration*", "supabase/**", "*.prisma"],
    "security_patterns": (r"(?i)authoriz|permission|\bowner|\brole\b|\btoken|password|secret|session|jwt|oauth|csrf|"
                          r"\brls\b|policy|current_user|login_required|req\.user|request\.user|getServerSession|"
                          r"\bselect\b.+\bfrom\b|insert\s+into|update\s+\w+\s+set|delete\s+from|\.execute\(|raw\(|"
                          r"tenant|\bacl\b"),
}


def config(cfg):
    """기본값 < 예산 모드(budget) < 사용자가 review에 직접 적은 값."""
    base = _lib._merge(DEFAULTS, _lib.budget(cfg).get("review") or {})
    return _lib._merge(base, (cfg or {}).get("review") or {})


def _git(proj, *args):
    return subprocess.run(["git", *args], cwd=proj, capture_output=True, text=True, timeout=30)


def changes(proj, rcfg, cfg):
    """커밋 이후 바뀐 코드 {경로: (추가, 삭제)}와 추가된 줄. 테스트 경로와 무시 경로는 뺀다. git이 아니면 None."""
    if _git(proj, "rev-parse", "--verify", "-q", "HEAD").returncode != 0:
        return None
    test_paths = (cfg.get("loop") or {}).get("test_paths") or []

    def wanted(rel):
        return (_lib.glob_match(rel, rcfg["code_paths"]) and not _lib.glob_match(rel, rcfg["ignore_paths"])
                and not _lib.glob_match(rel, test_paths))

    files, added = {}, []
    for line in _git(proj, "diff", "--numstat", "HEAD", "--").stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and wanted(parts[2]):
            files[parts[2]] = (int(parts[0]), int(parts[1]))
    if files:
        diff = _git(proj, "diff", "-U0", "--no-color", "HEAD", "--", *files).stdout
        added += [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    for rel in _git(proj, "ls-files", "--others", "--exclude-standard").stdout.splitlines():
        if wanted(rel):
            try:
                with open(os.path.join(proj, rel), encoding="utf-8", errors="replace") as f:
                    text = f.read().splitlines()
            except OSError:
                continue
            files[rel] = (len(text), 0)
            added += text
    return files, added


def fingerprint(proj, files):
    parts = []
    for rel in sorted(files):
        try:
            with open(os.path.join(proj, rel), "rb") as f:
                parts.append(rel + ":" + _lib.short_hash(f.read().decode("utf-8", "replace")))
        except OSError:
            parts.append(rel + ":gone")
    return _lib.short_hash("|".join(parts))


def sensitive(files, added, rcfg):
    if rcfg.get("security") == "always":
        return True
    if rcfg.get("security") == "never":
        return False
    if any(_lib.glob_match(rel, rcfg["security_paths"]) for rel in files):
        return True
    try:
        rx = re.compile(rcfg["security_patterns"])
    except re.error:
        return False
    return any(rx.search(line) for line in added)


def static_findings(proj, files, rcfg):
    """사다리의 첫 칸: 설치된 결정적 도구로 바뀐 파일만 빠르게 본다. 없거나 실패하면 빈 목록."""
    if not rcfg.get("static", True):
        return []
    py = [f for f in files if f.endswith(".py") and os.path.isfile(os.path.join(proj, f))]
    if not py or not shutil.which("ruff"):
        return []
    try:
        p = subprocess.run(["ruff", "check", "--quiet", "--no-cache", "--output-format", "concise",
                            "--select", "S,B,E9,F", "--ignore", "S101,B008", *py],
                           cwd=proj, capture_output=True, text=True, timeout=30)
    except Exception:
        return []
    return [ln for ln in p.stdout.splitlines() if ":" in ln][:10]


def _state(proj):
    """프로젝트마다 따로 둔다. 한 파일을 여러 세션이 동시에 읽고 쓰면 서로의 기록을 덮어써서
    횟수 제한이 풀린다 (실험에서 세 세션을 동시에 돌렸을 때 검토가 3~5번 반복된 원인)."""
    d = os.path.join(_lib.data_dir(), STATE_DIR)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, _lib.short_hash(os.path.realpath(proj)) + ".json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return path, data if isinstance(data, dict) else {}
    except Exception:
        return path, {}


def _save(path, mine):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(mine, f)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


FEEDBACK_RE = re.compile(r"^\s*Stop hook feedback|\[(review_gate|slop_judge|slop_scan)\]|^\s*\[harness\]|"
                         r"<task-notification|^\s*\[SYSTEM NOTIFICATION")


def on_prompt(event, proj):
    prompt = str(event.get("prompt") or "")
    if not prompt.strip() or FEEDBACK_RE.search(prompt[:400]):
        return  # 훅이 돌려준 피드백은 새 요청이 아니다
    path, mine = _state(proj)
    if mine.get("pending"):
        mine.pop("pending")  # 백그라운드 검토 결과 알림으로 열린 턴. 같은 요청이 이어진다
        _save(path, mine)
        return
    if mine:
        mine.update({"n": 0, "done_code": 0, "done_sec": 0})
        _save(path, mine)


def on_agent(event, proj, rcfg, cfg):
    ti = event.get("tool_input") or {}
    kind = str(ti.get("subagent_type") or "")
    resp = event.get("tool_response")
    is_async = bool(ti.get("run_in_background")) or (
        isinstance(resp, dict) and (resp.get("isAsync") or str(resp.get("status") or "").startswith("async")))
    key = "code" if kind.endswith("code-verifier") else "sec" if kind.endswith("security-reviewer") else None
    if not key:
        return
    ch = changes(proj, rcfg, cfg)
    if not ch or not ch[0]:
        return
    path, mine = _state(proj)
    mine[key] = fingerprint(proj, ch[0])
    mine["done_" + key] = int(mine.get("done_" + key) or 0) + 1
    if is_async:
        mine["pending"] = sorted(set(mine.get("pending") or []) | {key})
    _save(path, mine)


def on_stop(event, proj, rcfg, cfg):
    ch = changes(proj, rcfg, cfg)
    if not ch:
        return
    files, added = ch
    total = sum(a + d for a, d in files.values())
    if total < int(rcfg.get("min_lines") or 0):
        return
    try:
        if _lib.ledger_status(proj, cfg).get("state") == "fail":
            return  # 테스트가 깨진 상태면 검토보다 테스트가 먼저다
    except Exception:
        pass
    fp = fingerprint(proj, files)
    path, mine = _state(proj)
    if mine.get("pending"):
        return  # 백그라운드 검토 결과가 오는 중이다. 알림이 새 턴을 열어 반영한다
    rounds = max(int(rcfg.get("rounds") or 1), 1)
    if int(mine.get("n") or 0) >= rounds:
        return
    need_sec = sensitive(files, added, rcfg)
    need = []
    # 이번 요청에서 이미 rounds번 검토받았으면(스스로 부른 것 포함) 고친 뒤라도 다시 요구하지 않는다
    if mine.get("code") != fp and int(mine.get("done_code") or 0) < rounds:
        need.append(CODE_AGENT)
    if need_sec and mine.get("sec") != fp and int(mine.get("done_sec") or 0) < rounds:
        need.append(SEC_AGENT)
    if not need:
        return
    # 막는 순간 지금 내용을 요구한 것으로 적어 둔다. 무시하고 끝내도 같은 내용으로 다시 막지 않는다
    mine["n"] = int(mine.get("n") or 0) + 1
    if CODE_AGENT in need:
        mine["code"] = fp
    if SEC_AGENT in need:
        mine["sec"] = fp
    if not _save(path, mine):
        return
    names = sorted(files, key=lambda r: -sum(files[r]))
    listing = ", ".join(names[:8]) + (f" 외 {len(names) - 8}개" if len(names) > 8 else "")
    calls = [f"`{CODE_AGENT}`" for a in need if a == CODE_AGENT]
    if SEC_AGENT in need:
        model = rcfg.get("security_model") or "sonnet"
        calls.append(f"`{SEC_AGENT}`(model: {model})")
    agents = " 와 ".join(calls)
    static = static_findings(proj, files, rcfg)
    quick = rcfg.get("quick", True)
    _lib.audit(proj, HOOK, "block", names[0], f"{total}줄, {len(need)}개 검토")
    _lib.block_stop(
        f"[review_gate] 이번 변경(코드 {total}줄: {listing})을 끝내기 전에 독립 검토를 받으세요.\n"
        f"1. Agent 도구로 {agents}를 부르세요. 결과를 기다려야 하므로 run_in_background: false를 적습니다"
        f"{' (둘은 한 메시지에서 함께 불러도 됩니다)' if len(need) > 1 else ''}. "
        "프롬프트에는 사용자의 원래 요청, 바뀐 파일 목록, 그리고 \"검토 범위는 git diff HEAD와 새 파일뿐, 저장소 전체를 훑지 않는다\"를 적습니다."
        + (" 맨 앞에 \"빠른 검토\"라고 적어 보고서 파일 없이 고칠 것만 받습니다." if quick else "")
        + ("\n   정적 검사(ruff)가 먼저 찾은 것도 함께 넘기세요:\n   " + "\n   ".join(static) if static else "")
        + "\n"
        "2. 지적된 문제 중 이번 변경에서 생긴 것을 고치고, 테스트를 다시 돌립니다. 실제 요청으로 재현되는 문제만 고치고 "
        "이론상의 방어 코드는 늘리지 않습니다. 요청 밖의 일이거나 사용자 판단이 필요한 것은 고치지 말고 보고에 적습니다.\n"
        "3. 보고에 검토에서 나온 것과 고친 것을 짧게 남기고 끝냅니다. "
        "에이전트를 부를 수 없는 환경이면 /harness-core:risk-checklist 기준으로 직접 점검하고 끝내세요.")


def main():
    event = _lib.read_event()
    proj = _lib.project_dir(event)
    if not _lib.is_initialized(proj):
        return
    cfg = _lib.load_config(proj)
    rcfg = config(cfg)
    if rcfg.get("mode") == "off":
        return
    name = event.get("hook_event_name")
    if name == "UserPromptSubmit":
        on_prompt(event, proj)
    elif name == "PostToolUse" and event.get("tool_name") in ("Agent", "Task"):
        on_agent(event, proj, rcfg, cfg)
    elif name == "Stop":
        on_stop(event, proj, rcfg, cfg)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        try:
            _lib.audit(os.getcwd(), HOOK, "warn", "", "검사 오류: " + repr(exc))
        except Exception:
            pass
    sys.exit(0)
