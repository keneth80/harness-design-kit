"""harness-design 테스트: design_guard, capture.mjs(Playwright 있을 때), harness-full task_gate."""
import json
import shutil
import subprocess
import unittest

from helpers import HookCase, script

D, FULL = "harness-design", "harness-full"


class DesignGuard(HookCase):
    def edit(self, path, text, tool="Edit"):
        key = "content" if tool == "Write" else "new_string"
        ev = {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": {"file_path": path, key: text}}
        return self.context(self.run_hook(D, "design_guard.py", ev)[3])

    def tokens(self, **design):
        self.config(design={"tokens": ["src/styles/tokens.css"], **design})

    def test_silent_without_tokens(self):
        self.config()
        self.assertEqual(self.edit("src/Button.tsx", "<div style={{color: '#ff0044'}} />"), "")

    def test_flags_hardcoded_values(self):
        self.tokens()
        ctx = self.edit("src/Card.tsx", "\n".join([
            "<div className=\"bg-[#1a1a2e] text-[13px] p-4\">",
            "  <span style={{ color: 'rgb(200, 10, 10)', padding: 13 }}>x</span>",
            "</div>",
        ]))
        self.assertIn("bg-[#1a1a2e]", ctx)
        self.assertIn("text-[13px]", ctx)
        self.assertIn("rgb(", ctx)
        self.assertIn("4px 격자", ctx)
        self.assertIn("차단하지 않음", ctx)

    def test_accepts_tokens_and_grid_values(self):
        self.tokens()
        ok = "\n".join([
            ".card { background: var(--color-surface); padding: var(--space-4); }",
            "<div className=\"bg-surface p-4 text-sm\" style={{ padding: 16, borderWidth: 1 }} />",
            "// 주석의 #ff0000은 무시",
        ])
        self.assertEqual(self.edit("src/Card.tsx", ok), "")

    def test_id_selectors_are_not_colors(self):
        self.tokens()
        self.assertEqual(self.edit("src/a.css", "#add-button { margin: var(--space-2); }\n#bed { display: block; }"), "")

    def test_token_file_tests_and_svgs_skipped(self):
        self.tokens()
        self.assertEqual(self.edit("src/styles/tokens.css", ":root { --c: #123456; }"), "")
        self.assertEqual(self.edit("src/Card.test.tsx", "color: '#123456'"), "")
        self.assertEqual(self.edit("public/logo.svg", "<path fill=\"#123456\"/>"), "")

    def test_allow_list_and_off(self):
        self.tokens(allow=["#000"])
        self.assertEqual(self.edit("src/a.css", ".x { color: #000; }"), "")
        self.tokens(guard="off")
        self.assertEqual(self.edit("src/a.css", ".x { color: #123; }"), "")


@unittest.skipUnless(shutil.which("node") and subprocess.run(
    ["node", "-e", "require('playwright')"], capture_output=True).returncode == 0, "Playwright 필요")
class Capture(HookCase):
    PAGE = """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;font-family:sans-serif;background:#fff;color:#111}.low{color:#bbb}.wide{width:600px}
.tiny{width:16px;height:16px}</style></head><body><h1>제목</h1><p class="low">흐린 글씨</p>
<div class="wide">넓은 상자</div><button class="tiny"></button><img src="x.png"></body></html>"""

    def test_measures_known_issues(self):
        page = self.write("page.html", self.PAGE)
        r = subprocess.run(["node", str(script(D, "capture.mjs")), "--url", f"file://{page}", "--label", "t",
                            "--only", "mobile-light,desktop-dark"], capture_output=True, text=True, timeout=120,
                           cwd=self.proj, env=self.env())
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(r.stdout)
        s = report["summary"]
        self.assertEqual(s["shots"], 2)
        self.assertEqual(s["mobileOverflow"], ["t"])
        self.assertGreaterEqual(s["contrastIssues"], 1)
        self.assertGreaterEqual(s["unnamedControls"], 2)
        self.assertGreaterEqual(s["smallTapTargets"], 1)
        for rel in ("t-mobile-light.png", "t-desktop-dark.png", "t-report.json"):
            self.assertTrue((self.proj / "docs/design/shots" / rel).exists(), rel)

    def test_no_pages_is_an_error(self):
        r = subprocess.run(["node", str(script(D, "capture.mjs"))], capture_output=True, text=True,
                           cwd=self.proj, env=self.env())
        self.assertEqual(r.returncode, 2)
        self.assertIn("찍을 화면이 없습니다", r.stderr)


class TaskGate(HookCase):
    def complete(self, teammate="frontend"):
        ev = {"hook_event_name": "TaskCompleted", "task_id": "7", "task_subject": "로그인 화면",
              "teammate_name": teammate, "team_name": "session-abc"}
        return self.run_hook(FULL, "task_gate.py", ev)

    def test_solo_task_lists_untouched(self):
        self.config(verify={"lint": "exit 1"})
        self.assertEqual(self.complete(teammate="")[0], 0)

    def test_teammate_blocked_on_failing_lint(self):
        self.config(verify={"lint": "echo 'no-unused-vars' && exit 1"})
        code, _, err, _ = self.complete()
        self.assertEqual(code, 2)
        self.assertIn("no-unused-vars", err)
        self.assertIn("로그인 화면", err)

    def test_tests_not_run_and_disable(self):
        self.config(verify={"lint": "true", "test": "exit 1"})
        self.assertEqual(self.complete()[0], 0)
        self.config(verify={"lint": "exit 1"}, task_gate={"enabled": False})
        self.assertEqual(self.complete()[0], 0)

    def test_uninitialized_project_untouched(self):
        self.assertEqual(self.complete()[0], 0)


if __name__ == "__main__":
    unittest.main()
