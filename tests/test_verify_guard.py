"""verify_guard 회귀 테스트.

계약 검증:
  - 항상 exit 0 (차단하지 않음), 검증 실패는 stdout 경고
  - .claude/verify.json의 명령을 실행, run_on 패턴으로 대상 제한
의도적 린트 오류는 결정적 재현을 위해 "실패하는 린트 명령"으로 시뮬레이션한다
(ruff 등 실제 린터 설치 여부에 테스트가 좌우되지 않도록).
"""
import json
import tempfile
import unittest
from pathlib import Path

from helpers import edit_event, run_hook

HOOK = "verify_guard.py"
FAILING_LINT = 'python3 -c "print(\'foo.py:1:1 E999 intentional lint error\'); import sys; sys.exit(1)"'
PASSING_LINT = 'python3 -c "import sys; sys.exit(0)"'


class VerifyGuardTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_verify_json(self, cfg):
        d = self.proj / ".claude"
        d.mkdir(exist_ok=True)
        (d / "verify.json").write_text(json.dumps(cfg), encoding="utf-8")

    def test_intentional_lint_error_fires_warning(self):
        self._write_verify_json({"lint": FAILING_LINT, "run_on": ["*.py"]})
        code, out, err = run_hook(HOOK, edit_event(self.proj, "foo.py"))
        self.assertEqual(code, 0, "verify_guard는 실패해도 차단하지 않아야 함(exit 0)")
        self.assertIn("[verify_guard][경고]", out)
        self.assertIn("[lint]", out)
        self.assertIn("E999", out, "린트 출력 꼬리가 경고에 포함되어야 함")

    def test_passing_lint_is_silent(self):
        self._write_verify_json({"lint": PASSING_LINT, "run_on": ["*.py"]})
        code, out, err = run_hook(HOOK, edit_event(self.proj, "foo.py"))
        self.assertEqual(code, 0)
        self.assertEqual(out, "", "성공은 침묵해야 함")

    def test_run_on_filter_skips_unrelated_files(self):
        self._write_verify_json({"lint": FAILING_LINT, "run_on": ["*.py"]})
        code, out, _ = run_hook(HOOK, edit_event(self.proj, "README.md"))
        self.assertEqual(code, 0)
        self.assertEqual(out, "", "run_on 밖 파일 수정에는 발동하지 않아야 함")

    def test_no_config_no_markers_is_silent(self):
        # verify.json도, 프로젝트 마커(pyproject 등)도 없으면 아무것도 안 함
        code, out, _ = run_hook(HOOK, edit_event(self.proj, "foo.py"))
        self.assertEqual(code, 0)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
