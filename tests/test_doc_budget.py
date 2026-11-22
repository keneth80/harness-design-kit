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


class EntriesTest(HookCase):
    def test_entries_by_repeated_heading_level(self):
        head, items = doc_budget.entries(decisions(10))
        self.assertEqual(len(items), 10, "코드 블록 안의 ## 는 항목이 아니다")
        self.assertEqual(items[0]["title"], "D-001 결정 1")
        self.assertEqual(items[6]["status"], "대체")
        self.assertEqual(items[0]["date"], "2026-03-02")
        self.assertEqual(head, 4)

    def test_repeated_subheadings_are_not_entries(self):
        # ADR처럼 항목마다 배경·결정·결과 소제목이 되풀이되면 소제목이 아니라 ## 결정이 항목이다
        text = "# 결정\n\n" + "".join(f"## D-{i} 주제 {i}\n### 배경\n가\n### 결정\n나\n### 결과\n다\n\n" for i in range(1, 6))
        _, items = doc_budget.entries(text)
        self.assertEqual([i["title"] for i in items], [f"D-{i} 주제 {i}" for i in range(1, 6)])
        _, sub = doc_budget.entries(text, level=3)
        self.assertEqual(len(sub), 15)

    def test_index_section_keeps_numbers(self):
        text = decisions(5)
        with_index = text.replace("머리말입니다.\n\n", "머리말입니다.\n\n## 색인 (지금 유효한 것)\n| 번호 | 결정 |\n|---|---|\n| D-001 | 결정 1 |\n\n", 1)
        _, a = doc_budget.entries(text)
        head, b = doc_budget.entries(with_index)
        self.assertEqual([i["title"] for i in a], [i["title"] for i in b])
        self.assertEqual(head, 9, "머리말(색인 포함)은 첫 항목 전까지")

    def test_deeper_level_when_top_level_is_single(self):
        text = "# 교훈\n\n## 목록\n\n### L1 첫째\n본문\n### L2 둘째\n본문\n### L3 셋째\n본문\n\n## 부록\n끝\n"
        _, items = doc_budget.entries(text)
        self.assertEqual([i["title"] for i in items], ["L1 첫째", "L2 둘째", "L3 셋째"])
        self.assertEqual(items[2]["lines"], 3, "얕은 제목(## 부록)에서 끊는다")

    def test_cli_entries(self):
        self.write("docs/DECISIONS.md", decisions(9))
        p = self.run_script(CORE, "doc_budget.py", "--project", str(self.proj), "--entries", "docs/DECISIONS.md", "--json")
        data = json.loads(p.stdout)
        self.assertEqual(len(data["entries"]), 9)
        self.assertEqual(data["entries"][0]["line"], 5)


class ArchiveTest(HookCase):
    def setUp(self):
        super().setUp()
        self.original = decisions(12)
        self.write("docs/DECISIONS.md", self.original)

    def archive(self, *args):
        return self.run_script(CORE, "doc_budget.py", "--project", str(self.proj), "--archive", "docs/DECISIONS.md", *args)

    def test_moves_verbatim_and_leaves_stub(self):
        p = self.archive("--pick", "2,5-6", "--to", "docs/archive/decisions-2026.md")
        self.assertEqual(p.returncode, 0, p.stderr)
        res = json.loads(p.stdout)
        self.assertEqual(res["moved"], ["D-002 결정 2", "D-005 결정 5", "D-006 결정 6"])
        new = (self.proj / "docs/DECISIONS.md").read_text()
        arc = (self.proj / "docs/archive/decisions-2026.md").read_text()
        _, items = doc_budget.entries(self.original)
        for n in (2, 5, 6):
            it = items[n - 1]
            body = "".join(self.original.splitlines(keepends=True)[it["start"]:it["end"]])
            self.assertIn(body, arc, "글자 하나 바꾸지 않고 옮긴다")
            self.assertNotIn(body, new)
        self.assertIn("## D-002 결정 2 → 보관: [docs/archive/decisions-2026.md](archive/decisions-2026.md)", new)
        self.assertIn("## D-003 결정 3", new)
        self.assertTrue((self.proj / res["backup"]).read_text() == self.original)
        self.assertEqual((self.proj / ".harness/.gitignore").read_text(), "*\n")
        # 보관한 자리는 번호를 그대로 지키고, 다시 고르면 거절한다
        _, after = doc_budget.entries(new)
        self.assertEqual(len(after), 12)
        self.assertEqual(after[1]["status"], "보관됨")
        self.assertEqual(self.archive("--pick", "2", "--to", "docs/archive/decisions-2026.md").returncode, 1)

    def test_append_to_existing_archive_and_no_stub(self):
        self.archive("--pick", "1", "--to", "docs/archive/d.md")
        p = self.archive("--pick", "2", "--to", "docs/archive/d.md", "--no-stub")
        self.assertEqual(p.returncode, 0, p.stderr)
        arc = (self.proj / "docs/archive/d.md").read_text()
        self.assertEqual(arc.count("# 보관: DECISIONS.md"), 1)
        self.assertIn("## D-002 결정 2", arc)
        self.assertNotIn("D-002", (self.proj / "docs/DECISIONS.md").read_text())

    def test_rejects_bad_input(self):
        self.assertEqual(self.archive("--pick", "99", "--to", "docs/archive/d.md").returncode, 1)
        self.assertEqual(self.archive("--pick", "1", "--to", "docs/DECISIONS.md").returncode, 1)
        self.assertEqual(self.archive("--pick", "1", "--to", "../outside.md").returncode, 1)
        self.assertEqual(self.archive("--pick", "1").returncode, 2)
        self.assertEqual((self.proj / "docs/DECISIONS.md").read_text(), self.original)


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
