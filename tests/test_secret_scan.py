"""secret_scan 회귀 테스트.

계약 검증:
  - 시크릿 탐지 → exit 2 (사유 stderr), 깨끗한 코드 → exit 0 침묵
  - Supabase service_role JWT는 payload 디코딩으로 판별 (anon JWT는 통과)
  - placeholder·.env 로컬 파일은 오탐/스캔 제외
외부 도구(gitleaks/trufflehog) 의존 없이 결정적으로 돌도록 내장 패턴만 검증한다.
"""
import base64
import json
import tempfile
import unittest
from pathlib import Path

from helpers import run_hook

HOOK = "secret_scan.py"
NO_EXT = {"HARNESS_SECRET_SCAN_NO_EXTERNAL": "1"}


def make_jwt(payload_dict):
    b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    sig = ("Ab1Cd2Ef3" * 5)[:43]  # 실제 서명 형태 — 'xxxx' 등 placeholder 필터에 걸리지 않게
    return f"{b64({'alg': 'HS256', 'typ': 'JWT'})}.{b64(payload_dict)}.{sig}"


SERVICE_ROLE_JWT = make_jwt({"iss": "supabase", "role": "service_role", "exp": 9999999999})
ANON_JWT = make_jwt({"iss": "supabase", "role": "anon", "exp": 9999999999})

# 픽스처 키는 런타임에 결합 — 소스에 리터럴로 두면 GitHub push protection이
# 진짜 키로 오인해 푸시를 차단한다. 훅은 stdin으로 완성된 문자열을 받으므로 테스트는 유효.
FAKE_SB_SECRET = "sb_" + "secret_" + "TESTFAKEKEY1234567890abcd"
FAKE_GH_TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
FAKE_OPENAI_KEY = "sk-" + "abc123def456ghi789jkl012"


class SecretScanTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_event(self, file_path, content):
        return {
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content},
            "cwd": str(self.proj),
        }

    def _run(self, file_path, content):
        return run_hook(HOOK, self._write_event(file_path, content), env_extra=NO_EXT)

    # ── 차단 케이스 ────────────────────────────────────────────

    def test_service_role_jwt_blocked(self):
        code, out, err = self._run("lib/db.ts", f'const key = "{SERVICE_ROLE_JWT}"')
        self.assertEqual(code, 2)
        self.assertIn("service_role", err)
        self.assertIn("로테이션", err)

    def test_openai_style_key_blocked(self):
        code, _, err = self._run("app.py", f'client = OpenAI(api_key="{FAKE_OPENAI_KEY}")')
        self.assertEqual(code, 2)
        self.assertIn("secret_scan", err)

    def test_supabase_secret_key_blocked(self):
        code, _, err = self._run("config.py", f'KEY = "{FAKE_SB_SECRET}"')
        self.assertEqual(code, 2)

    def test_private_key_blocked(self):
        code, _, _ = self._run("deploy/id_rsa.py", 'PEM = """-----BEGIN RSA PRIVATE KEY-----"""')
        self.assertEqual(code, 2)

    def test_edit_new_string_scanned(self):
        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "a.ts", "old_string": "x",
                           "new_string": f'token = "{FAKE_GH_TOKEN}"'},
            "cwd": str(self.proj),
        }
        code, _, err = run_hook(HOOK, event, env_extra=NO_EXT)
        self.assertEqual(code, 2, "Edit의 new_string도 스캔되어야 함")

    # ── 통과 케이스 ────────────────────────────────────────────

    def test_anon_jwt_passes(self):
        code, out, err = self._run("lib/client.ts", f'const anon = "{ANON_JWT}"')
        self.assertEqual(code, 0, "anon 역할 JWT는 공개 가능 — 차단하면 안 됨")
        self.assertEqual(err, "")

    def test_clean_code_passes_silently(self):
        code, out, err = self._run("app.py",
                                   "import os\napi_key = os.environ['API_KEY']\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_placeholder_not_flagged(self):
        code, _, _ = self._run("README.md", 'api_key = "your-api-key-goes-here"')
        self.assertEqual(code, 0, "placeholder는 오탐하면 안 됨")

    def test_env_local_file_skipped(self):
        code, _, _ = self._run(".env", f"SUPABASE_SERVICE_ROLE_KEY={SERVICE_ROLE_JWT}\n")
        self.assertEqual(code, 0, ".env는 로컬 시크릿 보관처 — 스캔 제외")

    def test_env_example_still_scanned(self):
        code, _, _ = self._run(".env.example", f"SUPABASE_SERVICE_ROLE_KEY={SERVICE_ROLE_JWT}\n")
        self.assertEqual(code, 2, ".env.example에 실키가 들어가면 차단해야 함")

    def test_lock_file_skipped(self):
        code, _, _ = self._run("package-lock.json", f'"integrity": "{FAKE_OPENAI_KEY}"')
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
