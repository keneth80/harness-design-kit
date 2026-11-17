"""AI 티 검사(slop_scan): 규칙, 추가된 줄만 보기, 훅 모드(warn/ask/off), 세션 중복 제거, 예외, CLI, verify 연동."""
import json
import subprocess
import sys

from helpers import HookCase, script

CORE = "harness-core"
sys.path.insert(0, str(script(CORE, "_lib.py").parent))
import _lib  # noqa: E402

HERO = """export function Hero() {
  return (
    <section className="bg-gradient-to-r from-purple-500 to-blue-500">
      <h1>🚀 Welcome to our platform</h1>
      <p>혁신적인 서비스로 원활한 경험을 — 지금</p>
      <button onClick={() => unlock()}>시작하기</button>
    </section>
  );
}
"""


def rules_of(found):
    return {f["rule"] for f in found}


class RuleTest(HookCase):
    def scan(self, rel, text, **slop):
        scfg = _lib.slop_config({"slop": slop})
        lines = text.splitlines()
        return _lib.slop_scan_lines(rel, list(enumerate(lines, 1)), scfg, lines)

    def test_ui_and_text_rules_in_component(self):
        got = rules_of(self.scan("src/Hero.tsx", HERO))
        self.assertTrue({"ui-purple-gradient", "ui-emoji-heading", "txt-welcome", "txt-dash", "txt-buzzword"} <= got)

    def test_emoji_only_line_in_markup(self):
        self.assertIn("ui-emoji-icon", rules_of(self.scan("src/A.tsx", "<h1>\n  <span aria-hidden>\n    🔮\n  </span>\n</h1>")))
        self.assertNotIn("ui-emoji-icon", rules_of(self.scan("src/A.tsx", "<p>오늘의 운세 🔮</p>")))

    def test_code_identifiers_are_not_text(self):
        # unlock()은 코드이지 글이 아니다. 문자열·태그 사이 글만 본다
        self.assertNotIn("txt-buzzword-en", rules_of(self.scan("src/A.tsx", "<button onClick={() => unlock()}>열기</button>")))
        self.assertIn("txt-buzzword-en", rules_of(self.scan("src/A.tsx", 'const t = "Unlock your potential";')))

    def test_markdown_skips_code_blocks_and_inline_code(self):
        md = "정상 문장입니다.\n```\n원활한 — 예시\n```\n`원활한` 표기는 코드입니다.\n"
        self.assertEqual(self.scan("docs/a.md", md), [])

    def test_korean_text_patterns(self):
        got = rules_of(self.scan("docs/a.md", "## ✨ 소개\n단순히 도구가 아니라 동반자입니다.\n기록하는 것이 가장 중요합니다.\n"
                                              "결론적으로, 좋습니다.\n고민하고 계신가요?\n"))
        self.assertEqual(got, {"txt-emoji-bullet", "txt-not-just", "txt-important", "txt-wrapup", "txt-hook-question"})

    def test_plain_text_is_clean(self):
        self.assertEqual(self.scan("docs/a.md", "생년월일과 태어난 시각을 넣으면 사주 원국을 계산합니다.\n결과는 3초 안에 나옵니다.\n"), [])
        self.assertEqual(self.scan("src/a.css", ".card { border-radius: 4px; background: #f4efe6; }"), [])

    def test_paths_decide_kinds(self):
        scfg = _lib.slop_config({})
        self.assertEqual(_lib.slop_kinds("src/a.tsx", scfg), {"ui", "text"})
        self.assertEqual(_lib.slop_kinds("src/a.css", scfg), {"ui"})
        self.assertEqual(_lib.slop_kinds("README.md", scfg), {"text"})
        self.assertEqual(_lib.slop_kinds("locales/ko.json", scfg), {"text"})
        self.assertEqual(_lib.slop_kinds("src/engine.py", scfg), set())
        self.assertEqual(_lib.slop_kinds("node_modules/x/a.tsx", scfg), set())
        self.assertEqual(_lib.slop_kinds("src/a.test.tsx", scfg), set())
        self.assertEqual(_lib.slop_kinds("CHANGELOG.md", scfg), set())

    def test_allow_ban_and_inline_exception(self):
        self.assertEqual(self.scan("a.md", "원활한 연결", allow=["txt-buzzword"]), [])
        self.assertEqual(self.scan("a.md", "원활한 연결", allow=["원활"]), [])
        self.assertEqual(self.scan("a.md", "원활한 연결 <!-- slop-ok -->"), [])
        got = self.scan("a.md", "운명을 바꾸는 사주", ban=["운명을 바꾸는", {"pattern": "대박\\s*운", "message": "과장"}])
        self.assertEqual(rules_of(got), {"ban-1"})
        got = self.scan("a.md", "올해 대박 운", ban=[{"pattern": "대박\\s*운", "message": "과장", "id": "hype"}])
        self.assertEqual(got[0]["rule"], "hype")
        self.assertEqual(got[0]["message"], "과장")
        # 잘못된 정규식은 그 항목만 버린다
        self.assertEqual(rules_of(self.scan("a.md", "원활한", ban=[{"pattern": "("}])), {"txt-buzzword"})

    def test_added_lines_counts_duplicates(self):
        self.assertEqual(_lib.slop_added("a\nb\n", "a\nb\nc\nb\n"), [(3, "c"), (4, "b")])
        self.assertEqual(_lib.slop_added("a\nb", "a\nb"), [])


class HookTest(HookCase):
    def setUp(self):
        super().setUp()
        self.config()

    def hook(self, event, **env):
        event = {"cwd": str(self.proj), "session_id": "s1", **event}
        p = subprocess.run([sys.executable, str(script(CORE, "slop_scan.py")), "--hook"], input=json.dumps(event),
                           capture_output=True, text=True, timeout=30, env=self.env(**env))
        self.assertEqual(p.returncode, 0, p.stderr)
        out = p.stdout.strip()
        return json.loads(out) if out else None

    def post_write(self, rel, text, original=None):
        self.write(rel, text)
        return self.hook({"hook_event_name": "PostToolUse", "tool_name": "Write",
                          "tool_input": {"file_path": str(self.proj / rel), "content": text},
                          "tool_response": {"type": "update" if original else "create", "originalFile": original}})

    def test_warn_after_write(self):
        data = self.post_write("src/Hero.tsx", HERO)
        ctx = self.context(data)
        self.assertIn("[slop_scan]", ctx)
        self.assertIn("src/Hero.tsx:3 [ui-purple-gradient]", ctx)
        self.assertEqual(self.decision(data), "pass")

    def test_only_new_lines_on_rewrite(self):
        old = "<p>원활한 연결</p>\n"
        data = self.post_write("src/A.tsx", old + "<p>3초 안에 계산합니다</p>\n", original=old)
        self.assertIsNone(data)  # 원래 있던 줄은 다시 지적하지 않는다

    def test_edit_reports_line_number_in_file(self):
        self.write("src/A.tsx", "<div>\n<p>첫 줄</p>\n<p>혁신적인 기능</p>\n</div>\n")
        data = self.hook({"hook_event_name": "PostToolUse", "tool_name": "Edit",
                          "tool_input": {"file_path": str(self.proj / "src/A.tsx"),
                                         "old_string": "<p>기능</p>", "new_string": "<p>혁신적인 기능</p>"}})
        self.assertIn("src/A.tsx:3 [txt-buzzword]", self.context(data))

    def test_same_line_reported_once_per_session(self):
        self.assertIsNotNone(self.post_write("README.md", "원활한 연결\n"))
        self.assertIsNone(self.post_write("README.md", "원활한 연결\n"))
        self.assertIsNotNone(self.hook({"hook_event_name": "PostToolUse", "tool_name": "Write", "session_id": "s2",
                                        "tool_input": {"file_path": str(self.proj / "README.md"), "content": "원활한 연결\n"},
                                        "tool_response": {}}))

    def test_ask_mode_checks_before_write(self):
        self.config(slop={"mode": "ask"})
        self.write("src/A.tsx", "<div></div>\n")
        pre = {"hook_event_name": "PreToolUse", "tool_name": "Edit",
               "tool_input": {"file_path": str(self.proj / "src/A.tsx"), "old_string": "<div></div>",
                              "new_string": '<div className="from-violet-600 to-indigo-500"></div>'}}
        data = self.hook(pre)
        self.assertEqual(self.decision(data), "ask")
        self.assertIn("ui-purple-gradient", data["hookSpecificOutput"]["permissionDecisionReason"])
        # ask 모드에서 Post는 조용하다
        self.assertIsNone(self.post_write("README.md", "원활한 연결\n"))

    def test_warn_mode_pre_is_silent_and_off_mode_silent(self):
        pre = {"hook_event_name": "PreToolUse", "tool_name": "Write",
               "tool_input": {"file_path": str(self.proj / "README.md"), "content": "원활한 연결\n"}}
        self.assertIsNone(self.hook(pre))
        self.config(slop={"mode": "off"})
        self.assertIsNone(self.post_write("README.md", "원활한 연결\n"))

    def test_uninitialized_and_outside_paths_are_ignored(self):
        self.assertIsNone(self.post_write("src/engine.py", "x = '원활한'\n"))
        (self.proj / "harness.config.json").unlink()
        self.assertIsNone(self.post_write("README.md", "원활한 연결\n"))

    def test_broken_event_fails_open(self):
        p = subprocess.run([sys.executable, str(script(CORE, "slop_scan.py")), "--hook"], input="{not json",
                           capture_output=True, text=True, timeout=30, env=self.env())
        self.assertEqual((p.returncode, p.stdout.strip()), (0, ""))


class JudgeTest(HookCase):
    def setUp(self):
        super().setUp()
        self.git_init()
        self.config(slop={"judge": "stop"})
        subprocess.run(["git", "add", "-A"], cwd=self.proj, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cfg"], cwd=self.proj, check=True)

    def stop(self, active=False):
        event = {"cwd": str(self.proj), "session_id": "s1", "hook_event_name": "Stop", "stop_hook_active": active}
        p = subprocess.run([sys.executable, str(script(CORE, "slop_scan.py")), "--hook"], input=json.dumps(event),
                           capture_output=True, text=True, timeout=30, env=self.env())
        self.assertEqual(p.returncode, 0, p.stderr)
        out = p.stdout.strip()
        return json.loads(out) if out else None

    def blocked(self, data):
        return bool(data) and data.get("decision") == "block"

    def test_blocks_once_then_lets_stop(self):
        self.write("src/Hero.tsx", "<h1>사주</h1>\n")
        self.write("src/engine.py", "x = 1\n")
        data = self.stop()
        self.assertTrue(self.blocked(data))
        self.assertIn("harness-core:slop-judge", data["reason"])
        self.assertIn("src/Hero.tsx", data["reason"])
        self.assertNotIn("engine.py", data["reason"])
        self.assertIsNone(self.stop(active=True))  # 그대로면 다시 막지 않는다

    def test_rejudge_after_fix_up_to_rounds(self):
        self.write("README.md", "첫 문장\n")
        self.assertTrue(self.blocked(self.stop()))
        self.write("README.md", "고친 문장\n")
        self.assertTrue(self.blocked(self.stop(active=True)))  # 고친 뒤 재심사 (2번째)
        self.write("README.md", "또 고친 문장\n")
        self.assertIsNone(self.stop(active=True))  # judge_rounds(2)를 넘으면 그만
        self.write("README.md", "다음 요청에서 바꾼 문장\n")
        self.assertTrue(self.blocked(self.stop(active=False)))  # 새 요청이면 다시 센다

    def test_file_limit_and_rest_later(self):
        self.config(slop={"judge": "stop", "judge_max_files": 1})
        self.write("a.md", "a\n")
        self.write("b.md", "b\n")
        first = self.stop()["reason"]
        self.assertIn("넘기지 않은 파일 1개", first)
        second = self.stop(active=True)["reason"]
        self.assertNotEqual("a.md" in first, "a.md" in second)

    def test_own_judge_call_counts_as_judged(self):
        self.write("README.md", "글\n")
        event = {"cwd": str(self.proj), "session_id": "s1", "hook_event_name": "PostToolUse", "tool_name": "Agent",
                 "tool_input": {"subagent_type": "harness-core:slop-judge", "prompt": "README.md"}}
        p = subprocess.run([sys.executable, str(script(CORE, "slop_scan.py")), "--hook"], input=json.dumps(event),
                           capture_output=True, text=True, timeout=30, env=self.env())
        self.assertEqual((p.returncode, p.stdout.strip()), (0, ""))
        self.assertIsNone(self.stop())  # 이미 심사한 내용이면 막지 않는다
        self.write("README.md", "고친 글\n")
        self.assertTrue(self.blocked(self.stop(active=True)))

    def test_off_and_nothing_changed(self):
        self.assertIsNone(self.stop())
        self.write("README.md", "글\n")
        self.config(slop={"judge": "off"})
        self.assertIsNone(self.stop())


class CliAndVerifyTest(HookCase):
    def setUp(self):
        super().setUp()
        self.git_init()

    def cli(self, *args):
        return self.run_script(CORE, "slop_scan.py", "--project", str(self.proj), *args)

    def commit(self):
        subprocess.run(["git", "add", "-A"], cwd=self.proj, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c"], cwd=self.proj, check=True)

    def test_tree_scan_sees_changed_and_new_lines_only(self):
        self.write("README.md", "원활한 연결\n")
        self.commit()
        self.assertEqual(self.cli().returncode, 0)  # 커밋된 줄은 기준선
        self.write("README.md", "원활한 연결\n기록하는 것이 중요합니다.\n")
        self.write("src/New.tsx", "<h1>🚀 시작</h1>\n")
        p = self.cli("--json")
        self.assertEqual(p.returncode, 1)
        found = json.loads(p.stdout)["findings"]
        self.assertEqual({(f["file"], f["line"], f["rule"]) for f in found},
                         {("README.md", 2, "txt-important"), ("src/New.tsx", 1, "ui-emoji-heading")})

    def test_files_mode_and_rules(self):
        self.write("a.md", "결론적으로, 끝.\n")
        self.assertIn("txt-wrapup", self.cli("--files", "a.md").stdout)
        self.assertIn("ui-purple-gradient", self.cli("--rules").stdout)

    def test_verify_slop_check_enters_ledger(self):
        self.config(verify={"test": "true", "slop": True})
        self.commit()
        run = lambda: self.run_script(CORE, "verify_run.py", "--project", str(self.proj))  # noqa: E731
        p = run()
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertEqual([c["name"] for c in json.loads((self.proj / ".harness/verify-ledger.json").read_text())["checks"]],
                         ["test", "slop"])
        self.write("docs/intro.md", "원활한 연결\n")
        p = run()
        self.assertEqual(p.returncode, 1)
        out = json.loads(p.stdout)
        self.assertEqual(out["failures"][0]["name"], "slop")
        self.assertIn("txt-buzzword", out["failures"][0]["tail"])
