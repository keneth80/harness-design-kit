"""훅 테스트 공용 헬퍼.

훅 스크립트를 Claude Code가 부르는 방식 그대로 실행한다: stdin으로 이벤트 JSON을 넣고 stdout/exit를 본다.
테스트마다 HOME과 CLAUDE_PLUGIN_DATA를 임시 디렉터리로 바꿔 실제 사용자 설정·로그를 건드리지 않는다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"


def script(plugin, name):
    return PLUGINS / plugin / "scripts" / name


class HookCase(unittest.TestCase):
    """임시 프로젝트·HOME·플러그인 데이터 디렉터리를 갖춘 테스트 베이스."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.proj = base / "proj"
        self.home = base / "home"
        self.data = base / "data"
        for d in (self.proj, self.home, self.data):
            d.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    # ── 실행 ────────────────────────────────────────────────
    def env(self, **extra):
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "HARNESS_DEV",
                            "HARNESS_MONITOR", "HARNESS_NO_AUDIT")}
        env.update({"HOME": str(self.home), "CLAUDE_PLUGIN_DATA": str(self.data),
                    "CLAUDE_PROJECT_DIR": str(self.proj)})
        env.update({k: str(v) for k, v in extra.items()})
        return env

    def run_hook(self, plugin, name, event, timeout=60, **env_extra):
        event = {"cwd": str(self.proj), "session_id": "test-session", **event}
        proc = subprocess.run([sys.executable, str(script(plugin, name))], input=json.dumps(event),
                              capture_output=True, text=True, timeout=timeout, env=self.env(**env_extra))
        out = proc.stdout.strip()
        data = json.loads(out) if out.startswith("{") else None
        return proc.returncode, out, proc.stderr, data

    def run_script(self, plugin, name, *args, timeout=60, **env_extra):
        return subprocess.run([sys.executable, str(script(plugin, name)), *args], capture_output=True,
                              text=True, timeout=timeout, env=self.env(**env_extra))

    # ── 이벤트 ──────────────────────────────────────────────
    @staticmethod
    def bash(cmd):
        return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}}

    @staticmethod
    def tool(name, **tool_input):
        return {"hook_event_name": "PreToolUse", "tool_name": name, "tool_input": tool_input}

    # ── 판정 꺼내기 ────────────────────────────────────────
    @staticmethod
    def decision(data):
        if not data:
            return "pass"
        return (data.get("hookSpecificOutput") or {}).get("permissionDecision") or "pass"

    @staticmethod
    def context(data):
        return ((data or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")

    # ── 픽스처 ──────────────────────────────────────────────
    def write(self, rel, text):
        p = self.proj / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def config(self, **sections):
        cfg = {"version": 2, **sections}
        self.write("harness.config.json", json.dumps(cfg, ensure_ascii=False))

    def git_init(self):
        if shutil.which("git"):
            subprocess.run(["git", "init", "-q"], cwd=self.proj, check=True)
            subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                            "--allow-empty", "-m", "init"], cwd=self.proj, check=True)

    def audit_lines(self):
        p = self.data / "audit.jsonl"
        if not p.exists():
            return []
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
