"""lite 프로파일 회귀 테스트.

Claude Code에서 훅 발동 여부는 settings.json 등록이 결정하므로,
"은퇴/전환된 훅이 lite에서 발동하지 않는다" = "lite settings.json에 등록되어 있지 않다"를
검증한다. 추가로 switch.sh 왕복(lite→full→lite)과 두 템플릿 훅 사본의 동일성을 확인한다.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import CHATBOT, UNIVERSAL, registered_hook_scripts

LITE_HOOKS = {
    "security_gate.py", "drift_guard.py", "secret_scan.py", "verify_guard.py",
    "codemap_session.py", "codemap_refresh.py",
}
FULL_ONLY_HOOKS = {"code_reviewer.py", "backpressure.py", "report_generator.py"}
RETIRED_COMMANDS = {"commit.md", "pr-review.md"}
TEMPLATES = {"template-universal": UNIVERSAL, "template": CHATBOT}


class LiteProfileTest(unittest.TestCase):
    # ── 등록 기반: lite에서 은퇴/전환 훅이 발동하지 않는다 ──────

    def test_lite_settings_exclude_converted_hooks(self):
        for name, tpl in TEMPLATES.items():
            with self.subTest(template=name):
                scripts = registered_hook_scripts(tpl / ".claude" / "settings.json")
                self.assertEqual(
                    scripts & FULL_ONLY_HOOKS, set(),
                    f"{name}: lite 기본 settings.json에 full 전용 훅이 등록되어 있음",
                )
                self.assertEqual(scripts, LITE_HOOKS)

    def test_full_settings_keep_original_hooks(self):
        for name, tpl in TEMPLATES.items():
            with self.subTest(template=name):
                scripts = registered_hook_scripts(
                    tpl / ".claude" / "profiles" / "full" / "settings.json")
                self.assertTrue(FULL_ONLY_HOOKS <= scripts,
                                f"{name}: full 프로파일은 기존 훅 전체를 유지해야 함")
                self.assertTrue(LITE_HOOKS <= scripts)

    def test_retired_commands_removed_everywhere(self):
        for name, tpl in TEMPLATES.items():
            for sub in ("commands", "profiles/full/commands"):
                d = tpl / ".claude" / sub
                present = {p.name for p in d.glob("*.md")} & RETIRED_COMMANDS
                self.assertEqual(present, set(),
                                 f"{name}/{sub}: 은퇴 커맨드가 남아 있음: {present}")

    def test_hook_scripts_not_deleted(self):
        # 훅 스크립트 자체는 존치 — full 복원을 위해 삭제하면 안 됨
        for name, tpl in TEMPLATES.items():
            hooks = {p.name for p in (tpl / ".claude" / "hooks").glob("*.py")}
            self.assertTrue((LITE_HOOKS | FULL_ONLY_HOOKS) <= hooks,
                            f"{name}: 훅 스크립트가 삭제됨")

    def test_templates_share_identical_hook_scripts(self):
        uni_hooks = UNIVERSAL / ".claude" / "hooks"
        chat_hooks = CHATBOT / ".claude" / "hooks"
        for p in uni_hooks.glob("*.py"):
            with self.subTest(hook=p.name):
                other = chat_hooks / p.name
                self.assertTrue(other.exists(), f"template에 {p.name} 없음")
                self.assertEqual(p.read_bytes(), other.read_bytes(),
                                 f"{p.name}: 두 템플릿 사본이 어긋남")

    # ── switch.sh 왕복 ──────────────────────────────────────────

    def test_switch_roundtrip_universal(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "proj"
            shutil.copytree(UNIVERSAL, proj)
            switch = proj / ".claude" / "profiles" / "switch.sh"

            def run(profile):
                r = subprocess.run(["bash", str(switch), profile],
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 0, r.stderr)

            lite_cmds = {p.name for p in (proj / ".claude" / "commands").glob("*.md")}
            run("full")
            full_cmds = {p.name for p in (proj / ".claude" / "commands").glob("*.md")}
            self.assertIn("plan-start.md", full_cmds)
            self.assertIn("architect.md", {p.name for p in (proj / ".claude" / "agents").glob("*.md")})
            scripts = registered_hook_scripts(proj / ".claude" / "settings.json")
            self.assertTrue(FULL_ONLY_HOOKS <= scripts)

            run("lite")
            back_cmds = {p.name for p in (proj / ".claude" / "commands").glob("*.md")}
            self.assertEqual(back_cmds, lite_cmds, "lite 복귀 후 커맨드가 원상 복구되어야 함")
            scripts = registered_hook_scripts(proj / ".claude" / "settings.json")
            self.assertEqual(scripts & FULL_ONLY_HOOKS, set())

            run("lite")  # 멱등성: lite→lite 재실행이 에러 없이 동작

    def test_switch_rejects_unknown_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "proj"
            shutil.copytree(UNIVERSAL, proj)
            r = subprocess.run(
                ["bash", str(proj / ".claude" / "profiles" / "switch.sh"), "banana"],
                capture_output=True, text=True, timeout=30)
            self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
