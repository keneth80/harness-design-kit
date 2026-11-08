"""저장소 구조 검사: 매니페스트, 훅 경로, 스킬·에이전트 frontmatter, 공통 모듈 사본, v1 잔재."""
import filecmp
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"
MODELS = {"opus", "sonnet", "haiku", "inherit"}


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


class Layout(unittest.TestCase):
    def test_marketplace_lists_every_plugin(self):
        mp = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        listed = {p["name"]: p for p in mp["plugins"]}
        on_disk = {p.name for p in PLUGINS.iterdir() if p.is_dir()}
        self.assertEqual(set(listed), on_disk)
        for name, entry in listed.items():
            self.assertEqual(entry["source"], f"./plugins/{name}")
            manifest = json.loads((PLUGINS / name / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["name"], name)
            if name != "harness-core":
                self.assertIn("harness-core", manifest.get("dependencies", []))
                self.assertFalse(manifest.get("defaultEnabled", True), f"{name}은 프로젝트별로 켠다")

    def test_hook_scripts_exist(self):
        for hooks in PLUGINS.glob("*/hooks/hooks.json"):
            data = json.loads(hooks.read_text(encoding="utf-8"))
            for entries in data["hooks"].values():
                for entry in entries:
                    for h in entry["hooks"]:
                        m = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"]+)", h["command"])
                        self.assertIsNotNone(m, h["command"])
                        self.assertTrue((hooks.parent.parent / m.group(1)).exists(), m.group(1))

    def test_skills_have_description(self):
        skills = list(PLUGINS.glob("*/skills/*/SKILL.md"))
        self.assertGreater(len(skills), 20)
        for s in skills:
            fm = frontmatter(s)
            with self.subTest(skill=str(s.relative_to(ROOT))):
                self.assertIsNotNone(fm)
                self.assertEqual(fm.get("name"), s.parent.name)
                self.assertGreater(len(fm.get("description", "")), 20)
                self.assertNotIn("trigger", fm, "v1의 trigger는 Claude Code가 읽지 않는 필드")

    def test_agents_use_model_aliases(self):
        for a in PLUGINS.glob("*/agents/*.md"):
            fm = frontmatter(a)
            with self.subTest(agent=a.name):
                self.assertIn(fm.get("model"), MODELS)
                self.assertTrue(fm.get("description"))

    def test_lib_copies_in_sync(self):
        src = PLUGINS / "harness-core" / "scripts" / "_lib.py"
        for copy in PLUGINS.glob("*/scripts/_lib.py"):
            self.assertTrue(filecmp.cmp(src, copy, shallow=False), f"{copy} — python3 tools/sync_lib.py 실행")

    def test_no_v1_leftovers(self):
        stale = re.compile(r"\.claude/hooks/|scaffold\.sh|switch\.sh|claude-(opus|sonnet|haiku)-\d|"
                           r"\{\{[A-Z_]+\}\}|secret_scan|security_gate|setup-claude-optimization")
        migration_docs = {PLUGINS / "harness-core" / "skills" / "init" / "SKILL.md"}  # v1 정리 절차라 v1 경로를 말해야 함
        for f in list(PLUGINS.rglob("*.md")) + list(PLUGINS.rglob("*.json")):
            if f in migration_docs:
                continue
            text = f.read_text(encoding="utf-8")
            with self.subTest(file=str(f.relative_to(ROOT))):
                self.assertIsNone(stale.search(text), stale.search(text) and stale.search(text).group(0))

    def test_workflow_agent_types_exist(self):
        for wf in PLUGINS.glob("*/workflows/*.js"):
            for ref in set(re.findall(r"agentType: [`']([\w-]+):([\w$\{\}-]+)[`']", wf.read_text(encoding="utf-8"))):
                plugin, name = ref
                names = ["backend-dev", "frontend-dev"] if "${" in name else [name]
                for n in names:
                    with self.subTest(workflow=wf.name, agent=f"{plugin}:{n}"):
                        self.assertTrue((PLUGINS / plugin / "agents" / f"{n}.md").exists())

    def front(self, path):
        text = path.read_text(encoding="utf-8")
        return text.split("\n---\n", 1)[0]

    def skill_path(self, ref):
        plugin, name = ref.split(":")
        return ROOT / "plugins" / plugin / "skills" / name / "SKILL.md"

    def test_worker_agents_preload_hidden_playbooks(self):
        """작업자 에이전트는 얇은 껍데기: 절차는 숨은 교본 스킬에 한 번만 있다."""
        import re
        workers = {"architect", "qa-tester", "qa-engineer", "backend-dev", "frontend-dev"}
        for name in workers:
            path = ROOT / "plugins/harness-full/agents" / f"{name}.md"
            with self.subTest(agent=name):
                text = path.read_text(encoding="utf-8")
                refs = re.findall(r"^  - (harness-[a-z]+:[a-z0-9-]+)$", text, re.M)
                self.assertEqual(len(refs), 1)
                pb = self.skill_path(refs[0])
                self.assertTrue(pb.exists(), refs[0])
                front = self.front(pb)
                self.assertIn("user-invocable: false", front)
                self.assertNotIn("disable-model-invocation", front, "끄면 에이전트가 미리 불러오지 못한다")
                self.assertLess(len(text.splitlines()), 25, "껍데기에 절차를 다시 쓰지 않는다")

    def test_fork_entries_point_to_existing_agents(self):
        import re
        for skill in (ROOT / "plugins").glob("*/skills/*/SKILL.md"):
            m = re.search(r"^agent: (harness-[a-z]+):([a-z0-9-]+)$", self.front(skill), re.M)
            if not m:
                continue
            with self.subTest(skill=str(skill.relative_to(ROOT))):
                self.assertIn("context: fork", self.front(skill))
                self.assertTrue((ROOT / "plugins" / m.group(1) / "agents" / f"{m.group(2)}.md").exists())
                self.assertNotRegex(skill.read_text(encoding="utf-8").split("\n---\n", 1)[1].lstrip(), r"^# ",
                                    "fork 본문은 명령형 단계로 (스킬 명세 같은 제목은 자기 호출을 부를 수 있다)")

    def test_removed_agents_are_gone_everywhere(self):
        gone = ["ui-planner", "ui-designer", "error-handler", "error-curator", "automation-dev", "browser-dev", "integration-dev"]
        for p in list((ROOT / "plugins").rglob("*")) + [ROOT / "README.md", ROOT / "docs/GUIDE.md"]:
            if p.is_file() and p.suffix in (".md", ".json", ".js", ".py"):
                text = p.read_text(encoding="utf-8")
                for g in gone:
                    self.assertNotIn(g, text, f"{p.relative_to(ROOT)}에 {g}")

    def test_guide_and_help_commands_exist(self):
        """사용 가이드와 /help 지도에 적힌 명령은 실제로 있어야 한다 (숨은 교본은 명령이 아니다)."""
        import re
        for doc in (ROOT / "docs/GUIDE.md", ROOT / "plugins/harness-core/skills/help/references/map.md"):
            cmds = set(re.findall(r"`/(harness-[a-z]+):([a-z0-9-]+)", doc.read_text(encoding="utf-8")))
            self.assertGreater(len(cmds), 25)
            for plugin, name in sorted(cmds):
                with self.subTest(doc=doc.name, cmd=f"{plugin}:{name}"):
                    skill = ROOT / "plugins" / plugin / "skills" / name / "SKILL.md"
                    wf = ROOT / "plugins" / plugin / "workflows" / f"{name}.js"
                    self.assertTrue(skill.exists() or wf.exists())
                    if skill.exists():
                        self.assertNotIn("user-invocable: false", self.front(skill))

    def test_grill_is_assumption_check(self):
        text = (ROOT / "plugins/harness-full/skills/grill/SKILL.md").read_text(encoding="utf-8")
        front = text.split("\n---\n", 1)[0]
        self.assertIn("disable-model-invocation: true", front, "직접 부를 때만 돈다")
        self.assertIn("최대 3개", front)
        self.assertNotIn("모든 분기가 해결될 때까지", text)

    def test_no_claude_md_inside_plugins(self):
        self.assertEqual(list(PLUGINS.glob("*/CLAUDE.md")), [], "플러그인 루트의 CLAUDE.md는 로드되지 않는다")


if __name__ == "__main__":
    unittest.main()
