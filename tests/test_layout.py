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

    def test_no_claude_md_inside_plugins(self):
        self.assertEqual(list(PLUGINS.glob("*/CLAUDE.md")), [], "플러그인 루트의 CLAUDE.md는 로드되지 않는다")


if __name__ == "__main__":
    unittest.main()
