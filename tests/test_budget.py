"""v2.13 토큰 절약: 예산 모드, 검토 사다리(정적 검사 → 빠른 검토 → 모델 선택), lean 위임, 같은 검증 실패 줄이기, 고정 컨텍스트 줄이기."""
import re
import shutil
import subprocess
import sys

from helpers import PLUGINS, HookCase, script

CORE = "harness-core"
sys.path.insert(0, str(script(CORE, "review_gate.py").parent))
import review_gate  # noqa: E402


def commit(proj):
    subprocess.run(["git", "add", "-A"], cwd=proj, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c"], cwd=proj, check=True)


class PresetTest(HookCase):
    def test_presets_and_overrides(self):
        self.assertEqual(review_gate.config({})["min_lines"], 40)
        self.assertEqual(review_gate.config({})["security_model"], "sonnet")
        lean = review_gate.config({"budget": "lean"})
        self.assertEqual((lean["min_lines"], lean["quick"]), (80, True))
        deep = review_gate.config({"budget": "thorough"})
        self.assertEqual((deep["security_model"], deep["rounds"], deep["quick"]), ("opus", 2, False))
        self.assertEqual(review_gate.config({"budget": "lean", "review": {"min_lines": 10}})["min_lines"], 10)
        self.assertEqual(review_gate.config({"budget": "nonsense"})["min_lines"], 40)


class LadderTest(HookCase):
    def setUp(self):
        super().setUp()
        self.git_init()

    def block(self, **cfg):
        self.config(**cfg)
        commit(self.proj)
        self.write("app/auth.py", "".join(f"def f{i}(token):\n    return eval(token)\n" for i in range(5)))
        data = self.run_hook(CORE, "review_gate.py", {"hook_event_name": "Stop", "stop_hook_active": False})[3]
        self.assertIsNotNone(data)
        return data["reason"]

    def test_balanced_is_quick_diff_only_sonnet(self):
        r = self.block(review={"min_lines": 5})
        self.assertIn("harness-core:security-reviewer`(model: sonnet)", r)
        self.assertIn("빠른 검토", r)
        self.assertIn("git diff HEAD", r)

    def test_thorough_uses_opus_full_report(self):
        r = self.block(budget="thorough", review={"min_lines": 5})
        self.assertIn("(model: opus)", r)
        self.assertNotIn("빠른 검토", r)

    def test_static_findings_first(self):
        if not shutil.which("ruff"):
            self.skipTest("ruff 없음")
        r = self.block(review={"min_lines": 5})
        self.assertIn("정적 검사(ruff)", r)
        self.assertIn("S307", r)


class LeanDelegateTest(HookCase):
    def start(self):
        return self.run_hook(CORE, "session_start.py", {"hook_event_name": "SessionStart", "source": "startup"})[3] or {}

    def test_lean_adds_delegation_line(self):
        self.git_init()
        self.config(budget="lean")
        ctx = self.context(self.start())
        self.assertIn("harness-core:implementer", ctx)
        self.assertIn("budget=lean", ctx)
        self.config()
        self.assertNotIn("implementer", self.context(self.start()))


class VerifyDedupeTest(HookCase):
    def test_same_failure_is_shortened(self):
        self.config(verify={"lint": "sh -c 'echo 같은 오류 줄; exit 1'", "run_on": ["*.py"]})
        ev = self.tool("Edit", file_path=str(self.proj / "a.py"), old_string="x", new_string="y")
        ev["hook_event_name"] = "PostToolUse"
        self.write("a.py", "y\n")
        first = self.context(self.run_hook(CORE, "verify_guard.py", ev)[3])
        second = self.context(self.run_hook(CORE, "verify_guard.py", ev)[3])
        self.assertIn("같은 오류 줄", first)
        self.assertIn("직전과 같은", second)
        self.assertNotIn("같은 오류 줄", second)


class FixedContextTest(HookCase):
    MANUAL = ["help", "scenarios", "goal", "domain-manual", "domain-refactor", "domain-interview", "code-review",
              "security-review", "dev-start", "init", "slim"]

    def frontmatter(self, path):
        return path.read_text(encoding="utf-8").split("---")[1]

    def test_workflow_commands_are_manual_only(self):
        for name in self.MANUAL:
            fm = self.frontmatter(PLUGINS / CORE / "skills" / name / "SKILL.md")
            self.assertIn("disable-model-invocation: true", fm, name)

    def test_preloaded_skills_stay_model_visible(self):
        for agent in (PLUGINS).glob("*/agents/*.md"):
            fm = self.frontmatter(agent)
            for ref in re.findall(r"^\s+-\s+(harness-[\w-]+):([\w-]+)", fm, re.M):
                skill = PLUGINS / ref[0] / "skills" / ref[1] / "SKILL.md"
                self.assertNotIn("disable-model-invocation: true", self.frontmatter(skill), f"{agent.name} → {ref}")

    def test_core_descriptions_budget(self):
        total = 0
        for path in list((PLUGINS / CORE).glob("skills/*/SKILL.md")) + list((PLUGINS / CORE).glob("agents/*.md")):
            fm = self.frontmatter(path)
            if "disable-model-invocation: true" in fm:
                continue
            for key in ("description", "when_to_use"):
                m = re.search(rf"^{key}:\s*(.*)$", fm, re.M)
                total += len(m.group(1)) if m else 0
        self.assertLess(total, 2600, f"core가 매 턴 싣는 설명 {total}자")
