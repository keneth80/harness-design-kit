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
        ship = [i["issue"] for i in report["results"][0]["ship"]]
        self.assertEqual(s["shipIssues"], len(ship), "변형이 2개여도 페이지당 한 번만 센다")
        for needle in ("<html lang>", "<title>", "og:image", "<main>", "keep-all"):
            self.assertTrue(any(needle in x for x in ship), needle)

    GOOD = """<!doctype html><html lang="ko"><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>예약 노트</title><meta name="description" content="미용실 예약을 한 화면에서">
<meta property="og:image" content="https://example.com/og.png">
<style>body{margin:0;font-family:sans-serif;color:#111;background:#fff}h1,h2{word-break:keep-all}
.skip{position:absolute;left:-999px}.skip:focus{left:8px}</style></head><body>
<a class="skip" href="#main">본문 바로가기</a><nav><a href="/">홈</a><a href="/price">요금</a></nav>
<main id="main"><h1>예약 전화 없이 하루를 시작하세요</h1><h2>세 단계면 끝납니다</h2></main></body></html>"""

    def test_finished_page_has_no_ship_issues(self):
        page = self.write("good.html", self.GOOD)
        r = subprocess.run(["node", str(script(D, "capture.mjs")), "--url", f"file://{page}", "--label", "g",
                            "--only", "desktop-light"], capture_output=True, text=True, timeout=120,
                           cwd=self.proj, env=self.env())
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(r.stdout)
        self.assertEqual(report["results"][0]["ship"], [])
        self.assertEqual(report["summary"]["shipIssues"], 0)

    def test_no_pages_is_an_error(self):
        r = subprocess.run(["node", str(script(D, "capture.mjs"))], capture_output=True, text=True,
                           cwd=self.proj, env=self.env())
        self.assertEqual(r.returncode, 2)
        self.assertIn("찍을 화면이 없습니다", r.stderr)


class LandingAndFinish(unittest.TestCase):
    """ai-design-skills에서 가져온 부분: 범위가 좁은지, 시각 값을 고정하지 않는지, 라이선스 고지가 있는지."""
    ROOT = script(D, "capture.mjs").parent.parent

    def read(self, rel):
        return (self.ROOT / rel).read_text(encoding="utf-8")

    def test_landing_skill_is_narrow_and_defers_visuals(self):
        text = self.read("skills/landing-page/SKILL.md")
        desc = text.split("\n---\n", 1)[0]
        self.assertIn("랜딩", desc)
        self.assertIn("대시보드", desc, "대시보드·앱 화면에는 쓰지 않는다고 밝혀야 한다")
        self.assertNotRegex(desc, r"모든|ANY|always|항상")
        self.assertNotRegex(text, r"Geist|Manrope|Poppins|#9B9B9B|cubic-bezier", "고정 시각 값은 가져오지 않는다")
        self.assertIn("덮어쓰지 않는다", text)

    def test_finish_rules_referenced(self):
        self.assertIn("finish.md", self.read("skills/design-review/references/rubric.md"))
        self.assertIn("finish.md", self.read("agents/design-critic.md"))
        self.assertIn("FINISH_RULE", self.read("workflows/design-polish.js"))
        self.assertIn("keep-all", self.read("skills/design-review/references/finish.md"))

    def test_third_party_notice(self):
        notice = self.read("THIRD_PARTY_NOTICES.md")
        for needle in ("Copyright (c) 2026 Elaya", "Copyright (c) 2026 Leonxlnx", "elayadesign/ai-design-skills"):
            self.assertIn(needle, notice)


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
