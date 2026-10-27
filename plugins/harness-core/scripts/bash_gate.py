#!/usr/bin/env python3
"""bash_gate: PreToolUse(Bash) 보안 게이트.

v1의 security_gate는 명령 문자열 전체에 정규식을 대는 방식이라 `head .env`는 통과시키고
`git commit -m 'fix reboot'`는 막는 문제가 있었다. 이 게이트는 명령을 토큰으로 나누고
파이프·체인 단위로 "어떤 프로그램이 어떤 인자를 받는지"를 보고 판정한다.

판정 (deny = 차단, ask = 사용자 확인)
  1. 파괴적 명령        rm -rf / ~ * ., mkfs, dd of=/dev, shutdown, 포크 폭탄   → deny
                         git push --force, reset --hard, clean -f, --no-verify     → ask
                         DROP/TRUNCATE, WHERE 없는 DELETE                          → ask
  2. 원격 스크립트 실행  curl|wget ... | sh                                         → deny
  3. 시크릿 접근         .env·키 파일을 읽는 모든 방법(cat/head/grep/python -c ...) → deny
                         git add <시크릿>                                          → deny
                         source .env, 시크릿 이름 변수 echo, 전체 env 출력          → ask
  4. 외부 전송           curl -d @file / -F / -T, nc, scp·rsync 원격               → security.exfil (기본 ask)
                         그 대상이 시크릿 파일이면                                  → deny
  5. 하네스 변조         플러그인 디렉터리 쓰기·삭제                                → deny
                         harness.config.json, .claude/settings*.json 쓰기          → security.config_edits (기본 ask)
                         claude plugin disable/uninstall                            → ask

설계 원칙: 비밀값은 에이전트 손에 닿지 않게 한다. 막을 땐 왜 막는지와 대안을 같이 알려준다.
"""
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

HOOK = "bash_gate"

SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "\n", "|&", ";;"}
REDIRECTS_OUT = {">", ">>", ">|", "&>", "&>>"}
REDIRECTS_IN = {"<"}
ENV_FILE_FLAGS = {"--env-file", "--env_file"}  # docker/podman --env-file .env 은 값을 출력하지 않는다
OPERATORS = re.compile(r"&>>|&&|\|\||>>|&>|>&|>\||<<<|<<|\|&|;;|[;&|()<>]")
WRAPPERS = {"sudo", "command", "nohup", "time", "nice", "exec", "builtin", "doas", "xargs"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
INTERPRETERS = {"python", "python3", "node", "ruby", "perl", "php", "deno", "bun", "osascript"}
READERS = {
    "cat", "tac", "head", "tail", "less", "more", "bat", "nl", "grep", "egrep", "fgrep", "rg",
    "ag", "awk", "gawk", "sed", "cut", "sort", "uniq", "strings", "xxd", "od", "hexdump",
    "base64", "base32", "openssl", "gpg", "diff", "cmp", "jq", "yq", "vim", "vi", "nano",
    "emacs", "code", "open", "pbcopy", "xclip", "wc", "column", "paste",
    "zip", "tar", "gzip", "7z", "curl", "wget", "http", "https", "nc", "ncat", "scp", "rsync",
    "sftp", "ftp", "mail", "sendmail",
}
META_ONLY = {"ls", "test", "[", "[[", "stat", "file", "touch", "mkdir", "realpath", "dirname",
             "basename", "chmod", "echo", "printf", "true", "false"}
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSW|PASSWORD|CREDENTIAL|PRIVATE)", re.I)
FORK_BOMB = re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:")
SQL_CLIENTS = {"psql", "mysql", "mariadb", "sqlite3", "duckdb", "mongosh", "mongo", "clickhouse-client",
               "cockroach", "sqlcmd", "supabase", "prisma", "turso", "pgcli", "mycli", "litecli"}
SQL_DROP = re.compile(r"\b(DROP\s+(TABLE|DATABASE|SCHEMA)|TRUNCATE\s+TABLE?)\b", re.I)
SQL_DELETE_NO_WHERE = re.compile(r"\bDELETE\s+FROM\s+[\w.\"`]+\s*(;|$|['\"])", re.I)


class Verdict:
    """가장 강한 판정 하나를 유지한다 (deny > ask)."""

    def __init__(self):
        self.level = None
        self.reasons = []

    def add(self, level, reason):
        if level not in ("deny", "ask"):
            return
        if level == "deny" and self.level != "deny":
            self.level, self.reasons = "deny", []
        if level == self.level or self.level is None:
            self.level = self.level or level
            if reason not in self.reasons:
                self.reasons.append(reason)


def tokenize(cmd):
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    out = []
    for tok in lexer:
        # shlex는 연속된 기호를 한 토큰으로 묶는다(");" "<(" 등) → 연산자 단위로 다시 쪼갠다
        if tok and all(c in ";&|()<>" for c in tok):
            out.extend(OPERATORS.findall(tok))
        else:
            out.append(tok)
    return out


def split_segments(tokens):
    """파이프·체인으로 나눈 세그먼트 목록. 각 원소는 (토큰들, 바로 앞 구분자)."""
    segs, cur, prev_sep = [], [], None
    for tok in tokens:
        if tok in SEPARATORS:
            if cur:
                segs.append((cur, prev_sep))
            cur, prev_sep = [], tok
        else:
            cur.append(tok)
    if cur:
        segs.append((cur, prev_sep))
    return segs


def program_of(seg):
    """환경변수 할당과 sudo 같은 래퍼를 건너뛴 실제 프로그램 이름과 그 인자."""
    i = 0
    while i < len(seg):
        tok = seg[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tok):
            i += 1
            continue
        name = os.path.basename(tok)
        if name in WRAPPERS or name == "env" and i + 1 < len(seg) and "=" in seg[i + 1]:
            i += 1
            continue
        return name, seg[i + 1:]
    return "", []


def split_redirects(args):
    """인자에서 리다이렉션 대상(읽기/쓰기)을 분리한다."""
    plain, reads, writes = [], [], []
    i = 0
    while i < len(args):
        tok = args[i]
        if tok in REDIRECTS_OUT or tok in (">&",):
            if i + 1 < len(args) and args[i + 1] not in ("1", "2", "-"):
                writes.append(args[i + 1])
            i += 2
            continue
        if tok in REDIRECTS_IN:
            if i + 1 < len(args):
                reads.append(args[i + 1])
            i += 2
            continue
        if re.fullmatch(r"\d", tok) and i + 1 < len(args) and args[i + 1] in REDIRECTS_OUT | {">&"}:
            i += 1  # 2> 같은 fd 번호
            continue
        plain.append(tok)
        i += 1
    return plain, reads, writes


def quoted_literals(code):
    return re.findall(r"""['"]([^'"\n]{1,300})['"]""", code)


class Gate:
    def __init__(self, proj, cfg):
        self.proj = proj
        self.cfg = cfg
        self.sec = cfg.get("security") or {}
        self.v = Verdict()

    # ── 경로 분류 ───────────────────────────────────────────────
    def secret(self, path):
        return bool(path) and _lib.is_secret_path(path, self.cfg)

    def plugin_path(self, path):
        return _lib.is_plugin_path(_lib.abspath_in(self.proj, path))

    def config_path(self, path):
        return _lib.is_protected_config(_lib.abspath_in(self.proj, path), self.proj)

    # ── 쓰기 대상 점검 (변조 방지) ──────────────────────────────
    def check_write_target(self, path, how):
        if self.plugin_path(path):
            self.v.add("deny", f"하네스 플러그인 파일을 {how}하려 합니다 ({path}). "
                               "검증기는 에이전트가 수정할 수 없습니다.")
        elif self.config_path(path):
            self.v.add(self.sec.get("config_edits", "ask"),
                       f"하네스/Claude 설정 파일을 {how}하려 합니다 ({path}). 의도한 변경인지 확인하세요.")

    # ── 세그먼트 분석 ──────────────────────────────────────────
    def analyze(self, cmd, depth=0):
        if depth > 3 or not cmd.strip():
            return
        if FORK_BOMB.search(cmd):
            self.v.add("deny", "포크 폭탄 패턴입니다.")
        for inner in re.findall(r"`([^`]*)`", cmd):  # 백틱 명령 치환
            self.analyze(inner, depth + 1)
        try:
            tokens = tokenize(cmd)
        except ValueError:
            self.fallback(cmd)
            return
        segs = split_segments(tokens)
        for idx, (seg, sep) in enumerate(segs):
            prog, args = program_of(seg)
            if not prog:
                continue
            plain, reads, writes = split_redirects(args)
            for w in writes:
                self.check_write_target(w, "덮어쓰기")
                # 시크릿 파일로 쓰는 것은 허용 (시크릿은 원래 거기 있어야 한다)
            for r in reads:
                if self.secret(r):
                    self.v.add("deny", self.secret_msg(r))
            # 원격 스크립트 파이프 실행: curl ... | sh
            if prog in ("curl", "wget") and idx + 1 < len(segs) and segs[idx + 1][1] == "|":
                nxt, _ = program_of(segs[idx + 1][0])
                if nxt in SHELLS or nxt in INTERPRETERS:
                    self.v.add("deny", "원격 스크립트를 내려받아 바로 실행합니다. 스크립트를 먼저 받아서 내용을 확인하세요.")
            self.segment(prog, plain, depth)

    def segment(self, prog, args, depth):
        flags = [a for a in args if a.startswith("-")]
        operands = [a for i, a in enumerate(args)
                    if not a.startswith("-") and not (i > 0 and args[i - 1] in ENV_FILE_FLAGS)]

        # 중첩 셸: bash -c "...", eval "..."
        if prog in SHELLS and "-c" in args:
            i = args.index("-c")
            if i + 1 < len(args):
                self.analyze(args[i + 1], depth + 1)
            return
        if prog == "eval":
            self.analyze(" ".join(args), depth + 1)
            return

        # 1. 파괴적 명령
        if prog in SQL_CLIENTS or (prog == "docker" and "exec" in args):
            sql = " ".join(args)
            if SQL_DROP.search(sql):
                self.v.add("ask", "DROP/TRUNCATE 문이 포함되어 있습니다. 대상 DB가 맞는지 확인하세요.")
            if SQL_DELETE_NO_WHERE.search(sql):
                self.v.add("ask", "WHERE 없는 DELETE 문입니다.")
        if prog == "rm":
            recursive = any(re.match(r"^-[a-zA-Z]*[rR]", f) or f == "--recursive" for f in flags)
            for op in operands:
                if recursive and op in ("/", "/*", "~", "~/", "~/*", "$HOME", "${HOME}", "*", ".", "./", "..", "../"):
                    self.v.add("deny", f"광범위한 재귀 삭제입니다 (rm {' '.join(args)}).")
                self.check_write_target(op, "삭제")
        if prog.startswith("mkfs") or prog in ("shutdown", "reboot", "poweroff", "halt"):
            self.v.add("deny", f"시스템을 파괴하거나 종료하는 명령입니다 ({prog}).")
        if prog == "dd" and any(a.startswith("of=/dev/") for a in args):
            self.v.add("deny", "디스크 장치에 직접 씁니다 (dd of=/dev/...).")
        if prog == "chmod" and "777" in args:
            self.v.add("ask", "777 권한을 부여합니다.")
        if prog == "git" and args:
            self.git(args)
        if prog == "claude" and len(args) >= 2 and args[0] == "plugin" and args[1] in (
                "disable", "uninstall", "remove", "marketplace"):
            self.v.add("ask", f"플러그인 구성을 바꿉니다 (claude plugin {args[1]}).")

        # 5. 하네스 변조 (쓰기 계열 명령)
        if prog in ("mv", "cp", "ln", "install", "rsync") and operands:
            self.check_write_target(operands[-1], "덮어쓰기")
            if prog == "mv":
                for op in operands[:-1]:
                    self.check_write_target(op, "이동")
        if prog in ("tee", "truncate", "chown", "chmod", "shred", "unlink"):
            for op in operands:
                self.check_write_target(op, "수정")
        if prog in ("sed", "perl") and any(f.startswith("-i") or f == "--in-place" for f in flags):
            for op in operands:
                self.check_write_target(op, "제자리 수정")

        # 3. 시크릿 접근
        self.secrets(prog, args, flags, operands)
        self.recursive_grep(prog, args, flags, operands)

        # 4. 외부 전송
        self.exfil(prog, args, operands)

    def git(self, args):
        sub = args[0]
        rest = args[1:]
        if sub == "push" and any(a in ("--force", "-f", "--force-with-lease") or a.startswith("--force")
                                 or (a.startswith("+") and ":" in a) for a in rest):
            self.v.add("ask", "강제 푸시입니다. 원격 히스토리를 덮어씁니다.")
        if sub == "reset" and "--hard" in rest:
            self.v.add("ask", "git reset --hard는 커밋하지 않은 변경을 지웁니다.")
        if sub == "clean" and any(re.match(r"^-[a-zA-Z]*f", a) for a in rest):
            self.v.add("ask", "git clean -f는 추적하지 않는 파일을 지웁니다.")
        if sub in ("commit", "push", "merge", "rebase") and "--no-verify" in rest:
            self.v.add("ask", "--no-verify는 Git 훅(검증)을 건너뜁니다.")
        if sub == "add":
            for a in rest:
                if not a.startswith("-") and self.secret(a):
                    self.v.add("deny", f"시크릿 파일을 커밋하려 합니다 ({a}). .gitignore에 넣고 커밋에서 빼세요.")

    def secrets(self, prog, args, flags, operands):
        if prog in ("source", "."):
            for op in operands:
                if self.secret(op):
                    self.v.add("ask", f"시크릿 파일을 셸에 불러옵니다 ({op}). 값이 출력에 섞이지 않게 주의하세요.")
            return
        if prog in ("env", "printenv", "export", "set", "declare") and not operands:
            if prog != "export" or not args:
                self.v.add("ask", f"환경변수 전체를 출력합니다 ({prog}). 시크릿이 대화에 노출될 수 있습니다.")
            return
        if prog == "printenv" and any(SECRET_NAME.search(op) for op in operands):
            self.v.add("ask", "시크릿 이름의 환경변수 값을 출력합니다.")
            return
        if prog in ("echo", "printf"):
            joined = " ".join(args)
            if re.search(r"\$\{?[A-Za-z_]*(KEY|TOKEN|SECRET|PASSW|CREDENTIAL)[A-Za-z_]*\}?", joined, re.I):
                self.v.add("ask", "시크릿 이름의 환경변수 값을 출력합니다.")
            return
        if prog in INTERPRETERS:
            for i, a in enumerate(args):
                if a in ("-c", "-e", "-p", "--eval", "--print") and i + 1 < len(args):
                    for lit in quoted_literals(args[i + 1]):
                        if self.secret(lit):
                            self.v.add("deny", self.secret_msg(lit))
                    if re.search(r"os\.environ|process\.env|ENV\[|getenv", args[i + 1]) and \
                            re.search(r"print|console\.log|puts|echo|write", args[i + 1]):
                        self.v.add("ask", "코드로 환경변수 값을 출력합니다. 시크릿이 대화에 노출될 수 있습니다.")
        if prog == "git":
            return
        cp_sources = operands[:-1] if prog in ("cp", "mv", "scp", "rsync", "install") else operands
        for op in cp_sources:
            if not self.secret(op):
                continue
            if prog in META_ONLY:
                continue
            if prog in READERS or prog in INTERPRETERS or prog in ("cp", "mv", "install"):
                self.v.add("deny", self.secret_msg(op))
            else:
                self.v.add("ask", f"알 수 없는 프로그램({prog})이 시크릿 파일을 인자로 받습니다 ({op}).")
        # curl -d @.env, -F file=@.env 처럼 @로 파일을 넘기는 형태
        for a in args:
            if "@" in a:
                path = a.split("@", 1)[1].split(";")[0]
                if self.secret(path):
                    self.v.add("deny", self.secret_msg(path))

    def recursive_grep(self, prog, args, flags, operands):
        """grep -r는 .gitignore를 무시하고 .env까지 훑는다 (rg는 기본으로 건너뜀)."""
        if prog not in ("grep", "egrep", "fgrep"):
            return
        if not any(re.match(r"^-[a-zA-Z]*[rR]", f) or f in ("--recursive", "--dereference-recursive") for f in flags):
            return
        if any(f.startswith("--exclude") and ".env" in f for f in flags):
            return
        dirs = operands[1:] or ["."]  # 첫 operand는 검색 패턴
        for d in dirs:
            base = _lib.abspath_in(self.proj, d)
            try:
                names = os.listdir(base)
            except OSError:
                continue
            hits = [n for n in names if os.path.isfile(os.path.join(base, n)) and self.secret(n)]
            if hits:
                self.v.add("ask", f"grep -r가 시크릿 파일({', '.join(hits[:3])})까지 훑습니다. "
                                  "rg를 쓰거나(.gitignore를 따름) --exclude='.env*'를 붙이세요.")
                return

    def exfil(self, prog, args, operands):
        level = self.sec.get("exfil", "ask")
        if prog in ("curl", "http", "https", "xh"):
            uploading = False
            for i, a in enumerate(args):
                nxt = args[i + 1] if i + 1 < len(args) else ""
                if a in ("-T", "--upload-file") or a.startswith("--upload-file="):
                    uploading = True
                if a in ("-F", "--form") or a.startswith("--form="):
                    if "@" in nxt or "@" in a:
                        uploading = True
                if a in ("-d", "--data", "--data-binary", "--data-raw", "--data-urlencode") and nxt.startswith("@"):
                    uploading = True
                if re.match(r"^(-d|--data[\w-]*)=?@", a):
                    uploading = True
                if prog != "curl" and re.match(r"^[\w-]+@", a):
                    uploading = True
            if uploading:
                self.v.add(level, "로컬 파일을 외부로 업로드합니다. 대상 서버와 파일이 맞는지 확인하세요.")
        if prog in ("nc", "ncat", "netcat", "socat", "telnet"):
            self.v.add(level, f"원시 네트워크 연결을 엽니다 ({prog}).")
        if prog in ("scp", "sftp", "ftp") or (prog == "rsync" and any(
                re.match(r"^[^/\s]+:", op) for op in operands)):
            self.v.add(level, f"원격으로 파일을 전송합니다 ({prog}).")

    def fallback(self, cmd):
        """따옴표가 짝이 안 맞아 토큰화에 실패한 경우: 보수적으로 문자열을 훑는다."""
        for word in re.findall(r"[\w./~${}*-]+", cmd):
            if self.secret(word):
                self.v.add("ask", f"명령을 해석하지 못했는데 시크릿 파일 이름이 보입니다 ({word}).")
        if re.search(r"\brm\s+-[a-zA-Z]*[rR]", cmd) and re.search(r"\s(/|~|\$HOME|\*)\s*$", cmd):
            self.v.add("deny", "해석할 수 없는 광범위 재귀 삭제입니다.")

    @staticmethod
    def secret_msg(path):
        return (f"시크릿 파일 내용을 읽으려 합니다 ({path}). 비밀값은 에이전트가 직접 보지 않습니다. "
                "필요한 키 이름은 .env.example을 보고, 값이 필요하면 사용자에게 설정을 요청하세요.")


def main():
    event = _lib.read_event()
    if event.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (event.get("tool_input") or {}).get("command") or ""
    if not cmd.strip():
        sys.exit(0)
    proj = _lib.project_dir(event)
    try:
        cfg = _lib.load_config(proj)
        gate = Gate(proj, cfg)
        gate.analyze(cmd)
    except Exception as exc:  # 판정 로직 오류로 작업을 막지 않는다
        _lib.audit(proj, HOOK, "error", cmd, repr(exc))
        sys.exit(0)
    if gate.v.level:
        reason = " / ".join(gate.v.reasons)
        _lib.audit(proj, HOOK, gate.v.level, cmd, reason)
        _lib.decide(gate.v.level, f"[harness] {reason}")
    _lib.audit(proj, HOOK, "pass", cmd)
    sys.exit(0)


if __name__ == "__main__":
    main()
