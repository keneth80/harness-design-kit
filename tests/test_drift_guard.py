"""drift_guard 회귀 테스트 (v1 테스트 이식 + 경로 경계 버그 회귀).

v2 계약: 차단은 permissionDecision=deny JSON, 경고는 additionalContext(+systemMessage).
"""
import json
import unittest

from helpers import HookCase

P, S = "harness-core", "drift_guard.py"
COMPLETE = {"status": "complete", "open_questions": []}
INCOMPLETE = {"status": "in_progress", "open_questions": []}
BLOCKING = {"status": "complete", "open_questions": [{"question": "세션 만료 정책?", "blocks_completion": True}]}


class DriftGuard(HookCase):
    def domain(self, interview=None, code_paths=("backend/**", "frontend/**"), name="auth",
               last_synced="2099-12-31"):
        paths = "\n".join(f"  - {p}   # 구현 경로" for p in code_paths)
        self.write(f"docs/domains/{name}/manual.md",
                   f"```yaml\nlast_synced: {last_synced}   # 마지막 동기화\ninterview_status: n/a\n"
                   f"code_paths:\n{paths}\n```\n")
        if interview is not None:
            self.write(f"docs/domains/{name}/interview.json", json.dumps(interview, ensure_ascii=False))

    def edit(self, path="backend/auth.py"):
        return self.run_hook(P, S, self.tool("Edit", file_path=path, old_string="a", new_string="b"))

    def guard(self, **dg):
        self.config(drift_guard=dg)

    # 기본 차단
    def test_missing_interview_denied(self):
        self.domain(None)
        _, _, _, data = self.edit()
        self.assertEqual(self.decision(data), "deny")
        self.assertIn("interview.json이 없습니다", data["hookSpecificOutput"]["permissionDecisionReason"])

    def test_incomplete_interview_denied(self):
        self.domain(INCOMPLETE)
        self.assertEqual(self.decision(self.edit()[3]), "deny")

    def test_blocking_question_denied(self):
        self.domain(BLOCKING)
        _, _, _, data = self.edit()
        self.assertIn("세션 만료 정책", data["hookSpecificOutput"]["permissionDecisionReason"])

    def test_complete_interview_silent(self):
        self.domain(COMPLETE)
        code, out, err, _ = self.edit()
        self.assertEqual((code, out, err), (0, "", ""))

    def test_non_domain_and_docs_files_pass(self):
        self.domain(None, code_paths=("backend/**",))
        self.assertEqual(self.edit("scripts/tool.py")[1], "")
        self.assertEqual(self.edit("docs/domains/auth/manual.md")[1], "")

    def test_no_domains_dir_is_noop(self):
        self.assertEqual(self.edit()[1], "")

    # 경로 경계 (v1 버그: src/auth가 src/authz까지 잡았다)
    def test_prefix_respects_path_boundary(self):
        self.domain(None, code_paths=("src/auth",))
        self.assertEqual(self.decision(self.edit("src/auth/login.py")[3]), "deny")
        self.assertEqual(self.decision(self.edit("src/authz/policy.py")[3]), "pass")

    # 완화
    def test_warn_paths_downgrade(self):
        self.domain(None)
        self.guard(mode="block", warn_paths=["frontend/**"])
        _, _, _, data = self.edit("frontend/Login.tsx")
        self.assertEqual(self.decision(data), "pass")
        self.assertIn("완화 모드", self.context(data))
        self.assertIn("systemMessage", data)
        self.assertEqual(self.decision(self.edit("backend/auth.py")[3]), "deny")

    def test_trailing_slash_pattern(self):
        self.domain(None)
        self.guard(mode="block", warn_paths=["frontend/"])
        self.assertIn("완화 모드", self.context(self.edit("frontend/components/Button.tsx")[3]))

    def test_warning_never_grants_permission(self):
        self.domain(None)
        self.guard(mode="warn")
        _, _, _, data = self.edit()
        self.assertNotIn("permissionDecision", data["hookSpecificOutput"])

    def test_mode_off(self):
        self.domain(None)
        self.guard(mode="off")
        self.assertEqual(self.edit()[1], "")

    def test_invalid_or_broken_config_falls_back_to_block(self):
        self.domain(None)
        self.guard(mode="banana")
        self.assertEqual(self.decision(self.edit()[3]), "deny")
        self.write("harness.config.json", "{not json")
        self.assertEqual(self.decision(self.edit()[3]), "deny")

    def test_v1_config_still_works(self):
        self.domain(None)
        self.write("harness.config.json", json.dumps({"profile": "lite", "drift_guard": {"mode": "warn"}}))
        self.assertEqual(self.decision(self.edit()[3]), "pass")

    # Drift 경고
    def test_code_newer_than_manual_warns(self):
        self.domain(COMPLETE, last_synced="2000-01-01")
        self.write("backend/auth.py", "x = 1\n")
        ctx = self.context(self.edit()[3])
        self.assertIn("매뉴얼 동기화 이후", ctx)
        self.assertIn("인터뷰", ctx)  # interview.json도 last_synced보다 새로움


if __name__ == "__main__":
    unittest.main()
