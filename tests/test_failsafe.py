"""게이트가 고장 났을 때의 동작 (fail-safe).

판정 로직이나 공통 모듈이 실패하면 통과시키지 않고 ask로 돌린다. 정상 경로의 출력은 그대로 조용해야 한다.
세션 시작 때는 지난 알림 이후의 판정 오류를 한 번만 알린다.
"""
import datetime
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from helpers import HookCase, script

CORE = "harness-core"
BROKEN_CFG = {"security": {"secret_paths": 5}}  # 리스트 자리에 숫자: 판정 중 TypeError가 나는 실제 설정 실수


class GateErrors(HookCase):
    def test_bash_gate_error_asks(self):
        self.config(**BROKEN_CFG)
        code, _, _, data = self.run_hook(CORE, "bash_gate.py", self.bash("cat notes.txt"))
        self.assertEqual(code, 0)
        self.assertEqual(self.decision(data), "ask")
        self.assertIn("판정 중 오류", data["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIn("/harness-core:audit", data["systemMessage"])
        errors = [e for e in self.audit_lines() if e["result"] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["hook"], "bash_gate")

    def test_file_gate_error_asks(self):
        self.config(**BROKEN_CFG)
        _, _, _, data = self.run_hook(CORE, "file_gate.py", self.tool("Read", file_path=str(self.proj / "a.txt")))
        self.assertEqual(self.decision(data), "ask")
        self.assertTrue(data.get("systemMessage"))

    def test_malformed_event_outside_main_logic_asks(self):
        event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": "rm -rf /"}
        code, _, _, data = self.run_hook(CORE, "bash_gate.py", event)
        self.assertEqual(code, 0)
        self.assertEqual(self.decision(data), "ask")

    def test_normal_path_still_silent(self):
        self.config()
        for hook, event in (("bash_gate.py", self.bash("npm test")),
                            ("file_gate.py", self.tool("Read", file_path=str(self.proj / "src/a.ts")))):
            with self.subTest(hook=hook):
                code, out, err, _ = self.run_hook(CORE, hook, event)
                self.assertEqual((code, out), (0, ""))
        self.assertEqual(self.audit_lines(), [])


class BrokenLib(HookCase):
    """_lib.py가 문법 오류로 로드되지 않는 설치 상태를 흉내 낸다."""

    def run_copy(self, name, event):
        tmp = Path(tempfile.mkdtemp(dir=self.home))
        shutil.copy(script(CORE, name), tmp / name)
        (tmp / "_lib.py").write_text("def broken(:\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(tmp / name)], input=json.dumps(event),
                              capture_output=True, text=True, timeout=30, env=self.env())
        return proc.returncode, json.loads(proc.stdout)

    def test_gates_ask_when_lib_fails_to_load(self):
        for name, event in (("bash_gate.py", self.bash("cat .env")),
                            ("file_gate.py", self.tool("Read", file_path=".env"))):
            with self.subTest(gate=name):
                code, data = self.run_copy(name, event)
                self.assertEqual(code, 0)
                self.assertEqual(data["hookSpecificOutput"]["permissionDecision"], "ask")
                self.assertIn("SyntaxError", data["systemMessage"])
                self.assertIn("3.9", data["systemMessage"])


class SessionHealth(HookCase):
    def start(self, **env):
        return self.run_hook(CORE, "session_start.py", {"hook_event_name": "SessionStart", "source": "startup"}, **env)

    def log_error(self, hours_ago=0.0):
        ts = (datetime.datetime.now() - datetime.timedelta(hours=hours_ago)).isoformat(timespec="seconds")
        with open(self.data / "audit.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": ts, "hook": "bash_gate", "result": "error", "target": "x"}) + "\n")

    def test_recent_errors_reported_once(self):
        self.log_error(hours_ago=1)
        self.log_error(hours_ago=30)  # 24시간보다 오래된 것은 세지 않는다
        _, _, _, data = self.start()
        self.assertIn("판정 오류 1건", data["systemMessage"])
        self.assertIn("bash_gate", data["systemMessage"])
        self.assertEqual(self.start()[1], "", "같은 오류를 다음 세션에서 다시 알리지 않는다")

    def test_workflows_off_tells_the_model(self):
        _, _, _, data = self.start(CLAUDE_CODE_DISABLE_WORKFLOWS="1")
        ctx = self.context(data)
        self.assertIn("동적 워크플로우가 꺼져", ctx)
        self.assertIn("대신 수행하지 말고", ctx)
        self.assertEqual(self.start(CLAUDE_CODE_DISABLE_WORKFLOWS="0")[1], "")
