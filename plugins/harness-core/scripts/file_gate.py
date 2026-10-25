#!/usr/bin/env python3
"""file_gate: PreToolUse(Read|Grep|Write|Edit|MultiEdit|NotebookEdit) 보안 게이트.

v1의 secret_scan은 PostToolUse라서 시크릿이 이미 파일에 써진 뒤에 경고했다.
이 게이트는 "쓰기 전"에 내용을 보고 막는다. 그리고 Read 도구로 .env를 여는 경로도 막는다.

판정
  Read / Grep        시크릿 파일 읽기                         → deny
  Write / Edit 계열  하네스 플러그인 파일 수정                  → deny
                     harness.config.json, .claude/settings*.json → security.config_edits (기본 ask)
                     새로 쓰는 내용에 API 키·개인키·토큰         → deny  (.env 같은 시크릿 파일 자체는 예외)
                     주민등록번호·실제 카드번호(Luhn 통과)       → deny  (결제사 공식 테스트 카드는 허용)
"""
import base64
import fnmatch
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

HOOK = "file_gate"
READ_TOOLS = {"Read", "Grep"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

SECRET_SAMPLES = (".env", ".env.local", ".env.production", "server.key", "cert.pem", "id_rsa",
                  "credentials.json", "service-account.json", ".npmrc")
SKIP_SUFFIX = (".lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", ".min.js", ".min.css",
               ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf")

PLACEHOLDER = re.compile(
    r"(your[-_]|example|placeholder|changeme|dummy|sample|xxxx|\.\.\.|<[^>]*>"
    r"|\$\{|\{\{|process\.env|os\.environ|os\.getenv|import\.meta\.env|getenv\()", re.I)

SECRET_PATTERNS = [
    (r"sb_secret_[A-Za-z0-9_-]{10,}", "Supabase secret key"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}", "GitHub 토큰"),
    (r"github_pat_[A-Za-z0-9_]{22,}", "GitHub fine-grained PAT"),
    (r"sk-ant-[A-Za-z0-9_-]{20,}", "Anthropic API 키"),
    (r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", "OpenAI API 키"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack 토큰"),
    (r"AIza[0-9A-Za-z_-]{35}", "Google API 키"),
    (r"(?:sk|rk)_live_[A-Za-z0-9]{16,}", "Stripe live 키"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY", "개인키"),
    (r"(?i)(?:api[_-]?key|apikey|secret|token|passwd|password)\s*[=:]\s*[\"'][A-Za-z0-9+/_\-.]{16,}[\"']",
     "하드코딩 자격증명 의심"),
]
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.([A-Za-z0-9_-]{8,})\.[A-Za-z0-9_-]{8,}")

# 주민등록번호: 생년월일 6자리 - 성별코드(1~8) + 6자리
RRN_RE = re.compile(r"(?<!\d)(\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\s?-\s?([1-8])\d{6}(?!\d)")
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
TEST_CARDS = {
    "4242424242424242", "4000056655665556", "5555555555554444", "2223003122003222",
    "5200828282828210", "5105105105105100", "378282246310005", "371449635398431",
    "6011111111111117", "3056930009020004", "36227206271667", "3566002020360505",
    "6200000000000005", "4111111111111111", "4012888888881881", "4000000000000002",
    "4000000000009995", "4000000000000077", "4000002500003155",
}


def luhn_ok(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def jwt_is_service_role(payload_seg):
    try:
        seg = payload_seg + "=" * (-len(payload_seg) % 4)
        return "service_role" in base64.urlsafe_b64decode(seg).decode("utf-8", "replace")
    except Exception:
        return False


def mask(s):
    return s[:8] + "…" if len(s) > 8 else s


def scan_secrets(text):
    findings = []
    for line in text.splitlines():
        if PLACEHOLDER.search(line):
            continue
        for pat, desc in SECRET_PATTERNS:
            m = re.search(pat, line)
            if m:
                findings.append(f"{desc} ({mask(m.group(0))})")
                break
        for m in JWT_RE.finditer(line):
            if jwt_is_service_role(m.group(1)):
                findings.append(f"Supabase service_role JWT ({mask(m.group(0))})")
    return findings


def scan_personal(text):
    findings = []
    if RRN_RE.search(text):
        findings.append("주민등록번호 형식")
    for m in CARD_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and digits not in TEST_CARDS and luhn_ok(digits) \
                and len(set(digits)) > 2:
            findings.append(f"카드번호 형식 (끝자리 {digits[-4:]})")
            break
    return findings


def gate_paths(proj, cfg, target):
    """쓰기 대상 경로 판정. (level, reason) 또는 (None, None)."""
    full = _lib.abspath_in(proj, target)
    if _lib.is_plugin_path(full):
        return "deny", (f"하네스 플러그인 파일은 에이전트가 수정할 수 없습니다 ({target}). "
                        "하네스 자체를 고치는 중이면 사용자에게 HARNESS_DEV=1로 다시 실행해 달라고 하세요.")
    if _lib.is_protected_config(full, proj):
        level = (cfg.get("security") or {}).get("config_edits", "ask")
        return level, f"하네스/Claude 설정 파일을 수정합니다 ({target}). 검증을 약하게 만드는 변경인지 확인하세요."
    return None, None


def main():
    event = _lib.read_event()
    tool = event.get("tool_name", "")
    if tool not in READ_TOOLS | WRITE_TOOLS:
        sys.exit(0)
    proj = _lib.project_dir(event)
    target = _lib.tool_target(event)
    try:
        cfg = _lib.load_config(proj)
        level, reason = None, None

        if tool in READ_TOOLS:
            glob_pat = (event.get("tool_input") or {}).get("glob") or ""
            hit = target if target and _lib.is_secret_path(target, cfg) else ""
            if not hit and glob_pat:
                # Grep의 glob이 시크릿 파일을 훑는 패턴(.env* 등)인지 대표 파일명으로 확인
                samples = [n for n in SECRET_SAMPLES if _lib.is_secret_path(n, cfg)]
                if any(fnmatch.fnmatch(n, glob_pat) for n in samples):
                    hit = glob_pat
            if hit:
                level = "deny"
                reason = (f"시크릿 파일은 에이전트가 직접 읽지 않습니다 ({hit}). "
                          "키 이름은 .env.example에서 확인하고, 값은 사용자에게 설정을 요청하세요.")
        else:
            level, reason = gate_paths(proj, cfg, target)
            if level != "deny" and not target.endswith(SKIP_SUFFIX):
                text = _lib.written_text(event)
                if text and not _lib.is_secret_path(target, cfg):
                    found = scan_secrets(text)
                    if found:
                        level = "deny"
                        reason = ("코드에 비밀값을 쓰려 합니다: " + ", ".join(found) +
                                  ". 환경변수에서 읽도록 바꾸고(.env + .env.example에 키 이름만), "
                                  "이미 노출된 키라면 사용자에게 로테이션을 권하세요.")
                    else:
                        personal = scan_personal(text)
                        if personal:
                            level = "deny"
                            reason = ("실제 개인정보로 보이는 값을 쓰려 합니다: " + ", ".join(personal) +
                                      ". 예시·테스트 데이터는 가짜 값(결제사 테스트 카드 등)을 쓰세요.")
    except Exception as exc:
        _lib.audit(proj, HOOK, "error", target, repr(exc))
        sys.exit(0)

    if level:
        _lib.audit(proj, HOOK, level, f"{tool} {target}", reason)
        _lib.decide(level, f"[harness] {reason}")
    _lib.audit(proj, HOOK, "pass", f"{tool} {target}")
    sys.exit(0)


if __name__ == "__main__":
    main()
