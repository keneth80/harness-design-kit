"""drift_guard 회귀 테스트.

계약 검증:
  - exit 2 = 차단 (사유는 stderr)
  - exit 0 = 허용. 경고는 stdout의 훅 JSON(hookSpecificOutput.additionalContext=모델용,
    systemMessage=사용자용)으로 전달. permissionDecision은 절대 넣지 않음(권한 우회 방지).
  - harness.config.json 없음 → 기존 동작(전체 차단) 유지 (하위 호환)
  - mode: block/warn/off 3단계 + warn_paths 경로 예외
"""
import json
import tempfile
import unittest
from pathlib import Path

from helpers import edit_event, make_domain_fixture, run_hook, write_config


def parse_warning(stdout):
    """훅 JSON 출력에서 additionalContext를 추출. JSON이 아니면 테스트 실패 유도로 None."""
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return None, None
    return data, data.get("hookSpecificOutput", {}).get("additionalContext", "")

HOOK = "drift_guard.py"
COMPLETE = {"status": "complete", "open_questions": []}
INCOMPLETE = {"status": "in_progress", "open_questions": []}
BLOCKING = {
    "status": "complete",
    "open_questions": [
        {"question": "세션 만료 정책?", "blocks_completion": True}
    ],
}


class DriftGuardTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, file_path="backend/auth.py"):
        return run_hook(HOOK, edit_event(self.proj, file_path))

    # ── 하위 호환: 설정 파일 없음 → 기존 전체 차단 ──────────────

    def test_no_config_missing_interview_blocks(self):
        make_domain_fixture(self.proj, interview=None)
        code, out, err = self._run()
        self.assertEqual(code, 2)
        self.assertIn("interview.json이 없습니다", err)
        self.assertEqual(out, "")

    def test_no_config_incomplete_interview_blocks(self):
        make_domain_fixture(self.proj, interview=INCOMPLETE)
        code, out, err = self._run()
        self.assertEqual(code, 2)
        self.assertIn("complete가 아닙니다", err)

    def test_no_config_blocking_question_blocks(self):
        make_domain_fixture(self.proj, interview=BLOCKING)
        code, out, err = self._run()
        self.assertEqual(code, 2)
        self.assertIn("미해결 필수 항목", err)

    def test_no_config_complete_interview_passes_silently(self):
        make_domain_fixture(self.proj, interview=COMPLETE)
        code, out, err = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertEqual(err, "")

    def test_non_domain_file_passes(self):
        make_domain_fixture(self.proj, interview=None, code_paths=("backend/**",))
        code, out, err = self._run("scripts/tool.py")
        self.assertEqual(code, 0)

    # ── warn_paths: frontend는 경고 강등, backend는 차단 유지 ──

    def test_warn_paths_frontend_warns_instead_of_block(self):
        make_domain_fixture(self.proj, interview=None)
        write_config(self.proj, {"mode": "block", "warn_paths": ["frontend/**"]})
        code, out, err = self._run("frontend/Login.tsx")
        self.assertEqual(code, 0, "warn_paths 경로는 차단하면 안 됨")
        data, ctx = parse_warning(out)
        self.assertIsNotNone(data, f"경고는 훅 JSON이어야 함: {out!r}")
        self.assertIn("interview.json이 없습니다", ctx, "차단 사유가 additionalContext로 강등되어야 함")
        self.assertIn("완화 모드", ctx)
        self.assertIn("systemMessage", data, "사용자 표시용 systemMessage도 있어야 함")
        self.assertEqual(err, "")

    def test_warning_json_never_bypasses_permissions(self):
        # permissionDecision "allow"는 권한 시스템을 우회하므로 경고 JSON에 절대 포함 금지
        make_domain_fixture(self.proj, interview=None)
        write_config(self.proj, {"mode": "warn"})
        _, out, _ = self._run("backend/auth.py")
        data, _ = parse_warning(out)
        self.assertIsNotNone(data)
        self.assertNotIn("permissionDecision", data.get("hookSpecificOutput", {}))

    def test_warn_paths_backend_still_blocks(self):
        make_domain_fixture(self.proj, interview=None)
        write_config(self.proj, {"mode": "block", "warn_paths": ["frontend/**"]})
        code, out, err = self._run("backend/auth.py")
        self.assertEqual(code, 2, "warn_paths 밖 경로는 계속 차단해야 함")
        self.assertIn("interview.json이 없습니다", err)

    def test_warn_paths_trailing_slash_pattern(self):
        make_domain_fixture(self.proj, interview=None)
        write_config(self.proj, {"mode": "block", "warn_paths": ["frontend/"]})
        code, out, _ = self._run("frontend/components/Button.tsx")
        self.assertEqual(code, 0)
        _, ctx = parse_warning(out)
        self.assertIn("완화 모드", ctx)

    # ── mode: warn / off / 오설정 폴백 ──────────────────────────

    def test_mode_warn_downgrades_everything(self):
        make_domain_fixture(self.proj, interview=BLOCKING)
        write_config(self.proj, {"mode": "warn"})
        code, out, err = self._run("backend/auth.py")
        self.assertEqual(code, 0)
        _, ctx = parse_warning(out)
        self.assertIn("미해결 필수 항목", ctx)
        self.assertEqual(err, "")

    def test_mode_off_disables_guard(self):
        make_domain_fixture(self.proj, interview=None)
        write_config(self.proj, {"mode": "off"})
        code, out, err = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertEqual(err, "")

    def test_invalid_mode_falls_back_to_block(self):
        make_domain_fixture(self.proj, interview=None)
        write_config(self.proj, {"mode": "banana"})
        code, _, err = self._run()
        self.assertEqual(code, 2, "알 수 없는 mode 값은 block으로 폴백해야 함")

    def test_broken_config_falls_back_to_block(self):
        make_domain_fixture(self.proj, interview=None)
        (self.proj / "harness.config.json").write_text("{not json", encoding="utf-8")
        code, _, _ = self._run()
        self.assertEqual(code, 2, "깨진 설정 파일은 기존 동작(차단) 유지해야 함")


if __name__ == "__main__":
    unittest.main()
