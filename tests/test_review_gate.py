"""v2.12 품질 게이트: 끝내기 전 독립 검토(review_gate), 커밋된 테스트만 보호, pytest·ruff 감지, 결함 체크리스트."""
import json
import subprocess
import sys

from helpers import ROOT, HookCase, script

CORE = "harness-core"
sys.path.insert(0, str(script(CORE, "_lib.py").parent))
import _lib  # noqa: E402

CODE = "harness-core:code-verifier"
SEC = "harness-core:security-reviewer"


def commit(proj, msg="c"):
    subprocess.run(["git", "add", "-A"], cwd=proj, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg], cwd=proj, check=True)


class ReviewGateTest(HookCase):
    def setUp(self):
        super().setUp()
        self.git_init()
        self.config(review={"min_lines": 5})
        commit(self.proj, "cfg")

    def gate(self, event):
        return self.run_hook(CORE, "review_gate.py", event)[3]

    def stop(self, active=False):
        return self.gate({"hook_event_name": "Stop", "stop_hook_active": active})

    def prompt(self):
        return self.gate({"hook_event_name": "UserPromptSubmit", "prompt": "다음 요청"})

    def agent(self, kind, background=False):
        return self.gate({"hook_event_name": "PostToolUse", "tool_name": "Agent",
                          "tool_input": {"subagent_type": kind, "prompt": "검토", "run_in_background": background}})

    def reason(self, data):
        self.assertIsNotNone(data)
        self.assertEqual(data.get("decision"), "block")
        return data["reason"]

    def test_plain_change_asks_code_review_only(self):
        self.write("app/math_utils.py", "".join(f"def f{i}(x):\n    return x + {i}\n" for i in range(5)))
        r = self.reason(self.stop())
        self.assertIn(CODE, r)
        self.assertNotIn(SEC, r)
        self.assertIn("run_in_background: false", r)

    def test_sensitive_change_asks_security_too(self):
        self.write("app/notes.py", "".join(f"def h{i}(user=current_user):\n    return {i}\n" for i in range(5)))
        self.assertIn(SEC, self.reason(self.stop()))
        self.write("app/x.py", "a = 1\n")
        commit(self.proj)
        self.write("app/auth.py", "".join(f"v{i} = {i}\n" for i in range(6)))  # 경로만으로도 민감
        self.prompt()
        self.assertIn(SEC, self.reason(self.stop()))

    def test_small_tests_docs_and_off_are_skipped(self):
        self.write("app/a.py", "x = 1\n")
        self.assertIsNone(self.stop(), "min_lines 미만")
        commit(self.proj)
        self.write("tests/test_a.py", "".join(f"def test_{i}():\n    assert {i} == {i}\n" for i in range(10)))
        self.write("docs/notes.md", "글\n" * 50)
        self.assertIsNone(self.stop(), "테스트와 문서만 바뀜")
        self.write("app/b.py", "y = 2\n" * 10)
        self.config(review={"mode": "off", "min_lines": 5})
        self.assertIsNone(self.stop())

    def test_once_per_request_then_new_request_rechecks(self):
        self.write("app/m.py", "z = 1\n" * 10)
        self.reason(self.stop())
        self.assertIsNone(self.stop(active=True), "같은 요청에서는 rounds(1)번만")
        self.write("app/m.py", "z = 2\n" * 10)
        self.assertIsNone(self.stop(active=True))
        self.prompt()
        self.reason(self.stop())  # 검토받지 않은 내용(z = 2)은 다음 요청에서 묻는다
        self.prompt()
        self.assertIsNone(self.stop(), "이미 요구한 내용이면 다시 묻지 않음")

    def test_hook_feedback_is_not_a_new_request(self):
        # 실제 세션에서 Stop 훅 피드백도 UserPromptSubmit으로 들어와 횟수가 초기화되며 검토가 세 번 반복됐다
        self.write("app/m.py", "z = 1\n" * 10)
        self.reason(self.stop())
        self.gate({"hook_event_name": "UserPromptSubmit", "prompt": "Stop hook feedback:\n[review_gate] 이번 변경..."})
        self.write("app/m.py", "z = 2\n" * 10)
        self.assertIsNone(self.stop(active=True))

    def test_own_review_then_fix_is_enough(self):
        self.write("app/m.py", "z = 1\n" * 10)
        self.agent(CODE)
        self.write("app/m.py", "z = 2\n" * 10)  # 검토 뒤 고침
        self.assertIsNone(self.stop(), "이번 요청에서 이미 검토받았으면 고친 뒤 다시 요구하지 않음")

    def agent_async(self, kind):
        return self.gate({"hook_event_name": "PostToolUse", "tool_name": "Agent",
                          "tool_input": {"subagent_type": kind, "prompt": "검토", "run_in_background": False},
                          "tool_response": {"isAsync": True, "status": "async_launched", "agentId": "a1"}})

    def test_async_review_waits_for_result_without_reset(self):
        # 실제 세션: run_in_background: false로 불러도 오래 걸리는 검토는 비동기로 돌았고, 결과 알림이 새 턴을 열었다
        self.write("app/m.py", "z = 1\n" * 10)
        self.agent(CODE)
        self.agent_async(SEC)
        self.assertIsNone(self.stop(), "결과가 오는 중이면 막지 않는다")
        self.gate({"hook_event_name": "UserPromptSubmit", "prompt": "보안 검토 결과 도착"})  # 알림 턴
        self.write("app/m.py", "z = 2\n" * 10)  # 결과를 보고 고침
        self.assertIsNone(self.stop(active=True), "같은 요청 안에서 이미 둘 다 검토받음")
        self.gate({"hook_event_name": "UserPromptSubmit", "prompt": "다음 기능도 해줘"})
        self.write("app/m.py", "z = 3\n" * 10)
        self.reason(self.stop())

    def test_failing_ledger_skips_review(self):
        self.config(review={"min_lines": 5}, verify={"test": "false"})
        self.write("app/m.py", "z = 1\n" * 10)
        self.run_script(CORE, "verify_run.py", "--project", str(self.proj))
        self.assertIsNone(self.stop())

    def test_uninitialized_and_non_git_are_quiet(self):
        (self.proj / "harness.config.json").unlink()
        self.write("app/m.py", "z = 1\n" * 10)
        self.assertIsNone(self.stop())


class CommittedTestsOnlyTest(HookCase):
    def setUp(self):
        super().setUp()
        self.git_init()
        self.config()

    def edit(self, rel, old, new):
        return self.decision(self.run_hook(CORE, "file_gate.py", self.tool(
            "Edit", file_path=str(self.proj / rel), old_string=old, new_string=new))[3])

    def test_new_test_file_is_not_guarded(self):
        self.write("tests/test_new.py", "def test_a():\n    assert 1\n    assert 2\n")
        self.assertEqual(self.edit("tests/test_new.py", "    assert 2\n", ""), "pass")

    def test_committed_test_is_guarded_against_head(self):
        self.write("tests/test_old.py", "def test_a():\n    assert 1\n")
        commit(self.proj)
        # 이번 작업에서 덧붙인 단언을 다시 빼는 것은 커밋 기준으로 약화가 아니다
        self.write("tests/test_old.py", "def test_a():\n    assert 1\n    assert 2\n")
        self.assertEqual(self.edit("tests/test_old.py", "    assert 2\n", ""), "pass")
        self.assertEqual(self.edit("tests/test_old.py", "    assert 1\n    assert 2\n", "    pass\n"), "ask")


class DetectTest(HookCase):
    def test_pytest_dir_without_project_file(self):
        self.write("tests/test_a.py", "def test_a():\n    assert 1\n")
        self.assertEqual(_lib.autodetect_checks(str(self.proj)), {"test": "python3 -m pytest -q -x"})

    def test_ruff_and_mypy_only_with_config(self):
        self.write("pyproject.toml", "[project]\nname='x'\n[tool.ruff]\nline-length=100\n[tool.mypy]\nstrict=true\n")
        self.write("tests/conftest.py", "")
        got = _lib.autodetect_checks(str(self.proj))
        self.assertEqual(got, {"test": "python3 -m pytest -q -x", "lint": "ruff check .", "typecheck": "python3 -m mypy ."})
        self.write("pyproject.toml", "[project]\nname='x'\n")
        self.assertNotIn("lint", _lib.autodetect_checks(str(self.proj)))


class ChecklistLayoutTest(HookCase):
    def test_reviewers_preload_checklist(self):
        agents = ROOT / "plugins/harness-core/agents"
        for name in ("code-verifier", "security-reviewer"):
            self.assertIn("harness-core:risk-checklist", (agents / f"{name}.md").read_text())
        skill = (ROOT / "plugins/harness-core/skills/risk-checklist/SKILL.md").read_text()
        self.assertGreaterEqual(skill.count("\n| "), 13)
        hooks = json.loads((ROOT / "plugins/harness-core/hooks/hooks.json").read_text())["hooks"]
        for ev in ("Stop", "UserPromptSubmit", "PostToolUse"):
            self.assertIn("review_gate.py", json.dumps(hooks[ev]))
