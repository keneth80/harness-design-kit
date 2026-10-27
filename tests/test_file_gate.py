"""file_gate 회귀 테스트 — 평범/주입/과잉 세 변형.

v1의 secret_scan은 쓰고 난 뒤(PostToolUse) 경고했다. file_gate는 쓰기 전에 막는다.
"""
import unittest

from helpers import HookCase

P, S = "harness-core", "file_gate.py"
OPENAI = "sk-proj-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"
ANTHROPIC = "sk-ant-" + "api03-" + "abcdefghijklmnopqrstuvwx"
AWS = "AKIA" + "IOSFODNN7EXAMPLQ"


class Base(HookCase):
    def verdict(self, tool, **ti):
        _, _, _, data = self.run_hook(P, S, self.tool(tool, **ti))
        return self.decision(data), data


class Normal(Base):
    def test_ordinary_reads_and_writes_pass(self):
        cases = [
            ("Read", {"file_path": "src/app.ts"}),
            ("Read", {"file_path": ".env.example"}),
            ("Grep", {"pattern": "TODO", "path": "src"}),
            ("Write", {"file_path": "src/config.ts",
                       "content": "export const apiKey = process.env.OPENAI_API_KEY;\n"}),
            ("Write", {"file_path": ".env.example", "content": "OPENAI_API_KEY=your-key-here\n"}),
            ("Edit", {"file_path": "src/pay.ts", "old_string": "a", "new_string": "const card = '4242 4242 4242 4242';"}),
            ("Write", {"file_path": "README.md", "content": "전화번호 010-1234-5678 형식 예시\n"}),
            ("Write", {"file_path": "src/ids.ts", "content": "const orderId = '1234567890123';\n"}),
        ]
        for tool, ti in cases:
            with self.subTest(tool=tool, ti=ti):
                self.assertEqual(self.verdict(tool, **ti)[0], "pass")

    def test_writing_key_into_key_file_is_allowed(self):
        self.assertEqual(self.verdict("Write", file_path="certs/dev.pem",
                                      content="-----BEGIN RSA PRIVATE KEY-----\nMIIEow")[0], "pass")

    def test_grep_with_ordinary_glob_passes(self):
        self.assertEqual(self.verdict("Grep", pattern="KEY", glob="*.ts")[0], "pass")

    def test_writing_secret_into_env_file_is_allowed(self):
        # 시크릿은 원래 .env에 있어야 한다
        self.assertEqual(self.verdict("Write", file_path=".env", content=f"OPENAI_API_KEY={OPENAI}\n")[0], "pass")


class Injected(Base):
    def test_reading_secret_files_denied(self):
        for path in [".env", "config/.env.local", "certs/server.key", "deploy/service-account-prod.json",
                     "/home/u/.ssh/id_rsa", "credentials.json"]:
            with self.subTest(path=path):
                self.assertEqual(self.verdict("Read", file_path=path)[0], "deny")

    def test_grep_into_env_denied(self):
        self.assertEqual(self.verdict("Grep", pattern="KEY", path=".env")[0], "deny")
        self.assertEqual(self.verdict("Grep", pattern="KEY", glob=".env*")[0], "deny")

    def test_hardcoded_keys_denied_before_write(self):
        cases = [
            ("Write", {"file_path": "src/llm.ts", "content": f"const key = '{OPENAI}';"}),
            ("Edit", {"file_path": "src/llm.py", "old_string": "x", "new_string": f"client = Anthropic(api_key='{ANTHROPIC}')"}),
            ("MultiEdit", {"file_path": "infra/aws.py", "edits": [{"old_string": "a", "new_string": f"KEY = '{AWS}'"}]}),
            ("Write", {"file_path": "src/keys.ts", "content": "const k = `-----BEGIN RSA PRIVATE KEY-----\nMIIEow`;"}),
        ]
        for tool, ti in cases:
            with self.subTest(tool=tool):
                decision, data = self.verdict(tool, **ti)
                self.assertEqual(decision, "deny")
                self.assertIn("환경변수", data["hookSpecificOutput"]["permissionDecisionReason"])

    def test_real_personal_data_denied(self):
        self.assertEqual(self.verdict("Write", file_path="seed.sql",
                                      content="INSERT INTO u VALUES ('900101-1234567');")[0], "deny")
        # Luhn을 통과하는 비테스트 카드번호
        self.assertEqual(self.verdict("Write", file_path="seed.json",
                                      content='{"card": "4539 1488 0343 6467"}')[0], "deny")


class Overreach(Base):
    def test_plugin_files_cannot_be_edited(self):
        target = str(self.home / ".claude" / "plugins" / "cache" / "x" / "scripts" / "bash_gate.py")
        decision, data = self.verdict("Edit", file_path=target, old_string="deny", new_string="pass")
        self.assertEqual(decision, "deny")
        self.assertIn("HARNESS_DEV", data["hookSpecificOutput"]["permissionDecisionReason"])

    def test_config_edits_ask(self):
        for path in ["harness.config.json", ".claude/settings.json", ".claude/settings.local.json",
                     str(self.home / ".claude" / "settings.json")]:
            with self.subTest(path=path):
                self.assertEqual(self.verdict("Write", file_path=path, content="{}")[0], "ask")

    def test_config_edits_can_be_denied(self):
        self.config(security={"config_edits": "deny"})
        self.assertEqual(self.verdict("Edit", file_path="harness.config.json",
                                      old_string="block", new_string="off")[0], "deny")

    def test_extra_secret_paths_from_config(self):
        self.config(security={"secret_paths": ["secrets/**"]})
        self.assertEqual(self.verdict("Read", file_path="secrets/prod.yaml")[0], "deny")


if __name__ == "__main__":
    unittest.main()
