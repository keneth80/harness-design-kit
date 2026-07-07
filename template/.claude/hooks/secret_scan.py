#!/usr/bin/env python3
"""
secret_scan: PostToolUse 훅 (Write|Edit|MultiEdit 대상)
전용 시크릿 유출 탐지. code_reviewer(AI 리뷰, full 전용)와 달리 LLM 없이 항상 동작한다.

판정:
  1) 내장 패턴 — API 키(OpenAI/Anthropic/AWS/GitHub/Slack/Google), private key,
     Supabase secret key, 하드코딩 자격증명 의심. JWT는 payload를 디코딩해
     service_role 클레임이면 차단(Supabase service_role 키 유출).
  2) gitleaks 또는 trufflehog가 설치돼 있으면 대상 파일을 추가 스캔(선택적 —
     미설치여도 내장 패턴만으로 동작. 새 의존성 강제 없음).
     HARNESS_SECRET_SCAN_NO_EXTERNAL=1 로 외부 도구 스캔을 끌 수 있다.

예외:
  - .env / .env.local 등 로컬 시크릿 보관 파일은 스캔하지 않는다(gitignore 전제).
    단 .env.example은 스캔한다(실키가 들어가면 안 되는 파일).
  - placeholder(your-api-key, ${...}, process.env 참조 등)는 무시.

입력: stdin JSON { tool_name, tool_input, cwd, ... }
종료: 0=허용, 2=차단(stderr가 Claude에게 피드백됨 — 제거·환경변수 이전·로테이션 안내)
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from monitor import log_event
except Exception:
    def log_event(*a, **k): pass

SKIP_FILES = [".lock", "package-lock", "yarn.lock", ".min.js", ".min.css", ".map",
              ".png", ".jpg", ".svg", ".ico", ".woff", ".ttf", "node_modules/", ".git/"]

# placeholder/참조 표현 — 같은 줄에 있으면 오탐으로 보고 무시
PLACEHOLDER = re.compile(
    r"(your[-_]|example|placeholder|changeme|dummy|sample|xxxx|\.\.\.|<[^>]*>"
    r"|\$\{|\{\{|process\.env|os\.environ|os\.getenv|import\.meta\.env)", re.I)

PATTERNS = [
    (r"sb_secret_[A-Za-z0-9_-]{10,}", "Supabase secret key"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}", "GitHub 토큰"),
    (r"github_pat_[A-Za-z0-9_]{22,}", "GitHub fine-grained PAT"),
    (r"sk-ant-[A-Za-z0-9-]{20,}", "Anthropic API 키"),
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI API 키"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack 토큰"),
    (r"AIza[0-9A-Za-z_-]{35}", "Google API 키"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY", "Private key"),
    (r"(?:api[_-]?key|apikey|secret|token|passwd|password)\s*[=:]\s*[\"'][A-Za-z0-9+/_\-\.]{16,}[\"']",
     "하드코딩 자격증명 의심"),
]

JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.([A-Za-z0-9_-]{8,})\.[A-Za-z0-9_-]{8,}")


def jwt_is_service_role(payload_seg):
    """JWT payload(base64url)를 디코딩해 service_role 클레임인지 확인."""
    try:
        seg = payload_seg + "=" * (-len(payload_seg) % 4)
        payload = base64.urlsafe_b64decode(seg).decode("utf-8", "replace")
        return "service_role" in payload
    except Exception:
        return False


def mask(s):
    return s[:10] + "…" if len(s) > 10 else s


def extract_written(data):
    """이벤트에서 (대상 파일 경로, 이번에 쓰인 내용)을 추출."""
    ti = data.get("tool_input", {}) or {}
    tn = data.get("tool_name", "")
    fp = ti.get("file_path", "") or ti.get("path", "") or ti.get("filePath", "")
    parts = []
    if tn == "Write":
        parts.append(ti.get("content", "") or ti.get("file_text", ""))
    else:  # Edit / MultiEdit — 키 이름 신구 변형 모두 수용
        for key in ("new_string", "new_str"):
            if ti.get(key):
                parts.append(ti[key])
        for e in ti.get("edits", []) or []:
            parts.append(e.get("new_string", "") or e.get("new_str", ""))
    return fp, "\n".join(p for p in parts if p)


def scan_builtin(content):
    findings = []
    for line in content.splitlines():
        if PLACEHOLDER.search(line):
            continue
        for pat, desc in PATTERNS:
            m = re.search(pat, line)
            if m:
                findings.append(f"{desc}: {mask(m.group(0))}")
                break  # 한 줄에 하나만 보고
        for m in JWT_RE.finditer(line):
            if jwt_is_service_role(m.group(1)):
                findings.append(f"Supabase service_role JWT: {mask(m.group(0))}")
    return findings


def scan_external(target_abs):
    """gitleaks/trufflehog가 있으면 파일 전체를 추가 스캔. 미설치·오류는 조용히 통과."""
    if os.environ.get("HARNESS_SECRET_SCAN_NO_EXTERNAL", "").strip() in ("1", "true", "on"):
        return []
    if not os.path.isfile(target_abs):
        return []
    findings = []
    try:
        if shutil.which("gitleaks"):
            # v8.19+ 는 `dir`, 이전 v8은 `detect --no-git -s` — 순서대로 시도
            for args in (["gitleaks", "dir", target_abs, "--no-banner"],
                         ["gitleaks", "detect", "--no-git", "--no-banner", "-s", target_abs]):
                r = subprocess.run(args, capture_output=True, text=True, timeout=15)
                if "unknown command" in (r.stderr or ""):
                    continue
                if r.returncode == 1:  # gitleaks: 1 = leaks found
                    findings.append("gitleaks 탐지: " + (r.stdout or r.stderr).strip()[-400:])
                break
        elif shutil.which("trufflehog"):
            r = subprocess.run(["trufflehog", "filesystem", "--no-update", "--fail", target_abs],
                               capture_output=True, text=True, timeout=15)
            if r.returncode == 183:  # trufflehog: 183 = findings
                findings.append("trufflehog 탐지: " + (r.stdout or r.stderr).strip()[-400:])
    except Exception:
        pass  # 외부 도구 문제로 작업을 막지 않는다
    return findings


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    fp, content = extract_written(data)
    if not fp or not content:
        sys.exit(0)
    if any(p in fp for p in SKIP_FILES):
        sys.exit(0)

    base = os.path.basename(fp)
    if base.startswith(".env") and base != ".env.example":
        sys.exit(0)  # 로컬 시크릿 보관 파일 — 스캔 제외

    cwd = data.get("cwd") or os.getcwd()
    target_abs = fp if os.path.isabs(fp) else os.path.abspath(os.path.join(cwd, fp))

    findings = scan_builtin(content) + scan_external(target_abs)

    if findings:
        log_event(cwd, "secret_scan", fp, "blocked")
        print("🛑 [secret_scan] 시크릿 유출 의심 — 커밋 전에 반드시 조치하세요.\n"
              f"파일: {fp}\n" + "\n".join(f"  - {f}" for f in findings) + "\n"
              "조치: ① 코드에서 제거하고 환경변수(.env, gitignore 확인)로 이전 "
              "② 이미 커밋/노출된 키는 즉시 로테이션 "
              "③ placeholder가 오탐된 경우 'your-key-here' 같은 명시적 표기 사용.",
              file=sys.stderr)
        sys.exit(2)

    log_event(cwd, "secret_scan", fp, "pass")
    sys.exit(0)


if __name__ == "__main__":
    main()
