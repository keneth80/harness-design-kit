"""doc_budget: 에이전트가 보는 문서 크기 점검(매번 실리는 문서 합계, 자주 읽는 문서 파일별), 세션 알림, 항목 나누기, 보관."""
import json
import sys

from helpers import HookCase, script

CORE = "harness-core"
sys.path.insert(0, str(script(CORE, "doc_budget.py").parent))
import doc_budget  # noqa: E402


def decisions(n, every_status=7):
    out = ["# 결정 기록\n\n머리말입니다.\n\n"]
    for i in range(1, n + 1):
        st = "대체됨" if i % every_status == 0 else "채택"
        out.append(f"## D-{i:03d} 결정 {i}\n\n- 날짜: 2026-03-{(i % 27) + 1:02d}\n- 상태: {st}\n\n"
                   + "결정의 배경과 이유를 적은 문장입니다.\n" * 8
                   + "\n```\n## 코드 안의 제목\n```\n\n")
    return "".join(out)


class BudgetTest(HookCase):
    def run_cli(self, *args):
        return self.run_script(CORE, "doc_budget.py", "--project", str(self.proj), *args)

    def test_always_docs_follow_imports_and_rules(self):
        self.write("CLAUDE.md", "# 규칙\n@docs/rules.md\n`@docs/skip.md`\n@../outside.md\n")
        self.write("docs/rules.md", "규칙\n@more.md\n")
        self.write("docs/more.md", "더\n")
        self.write("docs/skip.md", "안 실림\n")
        self.write(".claude/rules/style.md", "스타일\n")
        self.write(".claude/rules/api.md", "---\npaths:\n  - src/api/**\n---\n조건부\n")
        names = [rel for rel, _ in doc_budget.always_docs(str(self.proj))]
        self.assertEqual(names, ["CLAUDE.md", "docs/rules.md", "docs/more.md", ".claude/rules/style.md"])

    def test_report_thresholds_and_init_scope(self):
        self.write("CLAUDE.md", "규칙\n" * 150)
        self.write("docs/rules.md", "규칙\n" * 60)
        self.write("CLAUDE.md", "규칙\n" * 150 + "@docs/rules.md\n")
        self.write("DECISIONS.md", decisions(30))
        rep = doc_budget.report(str(self.proj), {}, initialized=False)
        self.assertTrue(rep["always_over"])  # 파일 하나는 200줄 안이지만 합계가 넘는다
        self.assertEqual(rep["read"], [], "init 안 한 프로젝트는 매번 실리는 문서만 본다")
        rep = doc_budget.report(str(self.proj), {"docs": {"always_lines": 500}}, initialized=True)
        self.assertFalse(rep["always_over"])
        big = {d["file"]: d for d in rep["read"]}
        self.assertTrue(big["DECISIONS.md"]["over"])
        self.assertEqual(big["DECISIONS.md"]["kind"], "decisions")

    def test_archive_folder_and_ignore_paths_are_not_counted(self):
        self.write("docs/archive/decisions-2025.md", decisions(40))
        self.write("docs/lessons-learned.md", "## L1\n교훈\n")
        files = [d["file"] for d in doc_budget.report(str(self.proj), {}, initialized=True)["read"]]
        self.assertEqual(files, ["docs/lessons-learned.md"])

    def test_tokens_estimate(self):
        self.assertEqual(doc_budget.tokens("abcd" * 10), 10)
        self.assertEqual(doc_budget.tokens("가나다라"), 4)

    def test_cli_report(self):
        self.config()
        self.write("DECISIONS.md", decisions(30))
        p = self.run_cli()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("DECISIONS.md", p.stdout)
        self.assertIn("초과", p.stdout)
        data = json.loads(self.run_cli("--json").stdout)
        self.assertEqual(data["read"][0]["file"], "DECISIONS.md")


class SlimAgentsTest(HookCase):
    def test_slim_agents_are_separate_and_scoped(self):
        agents = script(CORE, "doc_budget.py").parent.parent / "agents"
        slimmer = (agents / "doc-slimmer.md").read_text()
        checker = (agents / "slim-checker.md").read_text()
        self.assertIn("tools: Read, Grep, Glob, Write", slimmer)
        self.assertNotIn("Bash", slimmer.split("---")[1], "초안만 쓰고 명령은 돌리지 않는다")
        self.assertIn("tools: Read, Grep, Glob\n", checker, "검수자는 읽기 전용")
        skill = (script(CORE, "doc_budget.py").parent.parent / "skills/slim/SKILL.md").read_text()
        for name in ("harness-core:doc-slimmer", "harness-core:slim-checker", "docs/archive/", ".harness/slim-draft/"):
            self.assertIn(name, skill)
        self.assertNotIn("--archive", skill, "경량화는 스크립트가 아니라 AI가 한다")


class NoticeTest(HookCase):
    def start(self):
        return self.run_hook(CORE, "session_start.py", {"hook_event_name": "SessionStart", "source": "startup"})

    def test_session_start_notices_big_decisions_once(self):
        self.git_init()
        self.config()
        self.write("DECISIONS.md", decisions(30))
        msg = self.start()[3].get("systemMessage", "")
        self.assertIn("자주 읽는 문서", msg)
        self.assertIn("/harness-core:slim DECISIONS.md", msg)
        self.assertNotIn("DECISIONS", self.start()[3].get("systemMessage", ""), "같은 상태면 다시 알리지 않는다")
        self.write("DECISIONS.md", decisions(31))
        self.assertIn("DECISIONS.md", self.start()[3].get("systemMessage", ""))

    def test_notice_can_be_turned_off(self):
        self.git_init()
        self.config(docs={"notice": False})
        self.write("CLAUDE.md", "규칙\n" * 300)
        self.assertNotIn("CLAUDE.md", self.start()[3].get("systemMessage", ""))
