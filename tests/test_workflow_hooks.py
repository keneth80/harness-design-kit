"""워크플로우 훅 테스트: verify_guard, session_start, codemap_refresh, backpressure, init_project."""
import json
import shutil
import unittest

from helpers import HookCase, script

CORE, FULL = "harness-core", "harness-full"


class VerifyGuard(HookCase):
    def edit(self, path="src/a.py"):
        ev = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {"file_path": path}}
        return self.run_hook(CORE, "verify_guard.py", ev)

    def test_uninitialized_project_is_silent(self):
        self.write("package.json", json.dumps({"scripts": {"lint": "exit 1"}}))
        self.assertEqual(self.edit("src/a.ts")[1], "")

    def test_failure_reaches_model_context(self):
        self.config(verify={"lint": "echo 'E501 line too long' && exit 1", "run_on": ["*.py"]})
        _, _, _, data = self.edit()
        ctx = self.context(data)
        self.assertIn("E501", ctx)
        self.assertIn("차단은 하지 않습니다", ctx)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "PostToolUse")

    def test_success_is_silent(self):
        self.config(verify={"lint": "true", "typecheck": "true"})
        self.assertEqual(self.edit()[1], "")

    def test_run_on_filter(self):
        self.config(verify={"lint": "exit 1", "run_on": ["*.ts"]})
        self.assertEqual(self.edit("src/a.py")[1], "")

    def test_tests_skipped_on_edit_by_default(self):
        self.config(verify={"test": "exit 1"})
        self.assertEqual(self.edit()[1], "")

    def test_legacy_verify_json_used(self):
        self.config()
        self.write(".claude/verify.json", json.dumps({"lint": "echo legacy && exit 3"}))
        self.assertIn("legacy", self.context(self.edit()[3]))


class SessionStart(HookCase):
    def start(self, **env):
        return self.run_hook(CORE, "session_start.py", {"hook_event_name": "SessionStart", "source": "startup"}, **env)

    def make_sources(self, n):
        for i in range(n):
            self.write(f"src/m{i}.py", f"def f{i}():\n    return {i}\n")

    def test_initialized_injects_status_and_codemap(self):
        self.config()
        self.write("docs/codemap.md", "# 코드맵\n## src/\n### a.py\n- exports: def f()\n")
        ctx = self.context(self.start()[3])
        self.assertIn("하네스가 켜져 있습니다", ctx)
        self.assertIn("- src/ (1): a.py", ctx)
        self.assertNotIn("exports: def f()", ctx, "파일별 세부는 매 세션 싣지 않고 필요할 때 읽는다")

    def test_codemap_summary_is_capped_and_modes(self):
        big = "# 코드맵\n" + "".join(f"## pkg{d}/\n" + "".join(f"### mod{i}.py\n- exports: def f{i}()\n" for i in range(9))
                                    for d in range(80))
        self.write("docs/codemap.md", big)
        self.config()
        ctx = self.context(self.start()[3])
        self.assertLess(len(ctx), 2200, "요약은 1,500자 안팎")
        self.assertIn("- pkg0/ (9): mod0.py, mod1.py, mod2.py, mod3.py 외 5개", ctx)
        self.assertIn("폴더", ctx.split("\n")[-2] + ctx.split("\n")[-3])
        self.config(codemap={"inline": "full"})
        self.assertIn("exports: def f0()", self.context(self.start()[3]))
        self.config(codemap={"inline": "off"})
        self.assertNotIn("코드맵", self.context(self.start()[3]))

    def test_long_claude_md_noticed_once(self):
        self.git_init()
        self.config()
        self.write("CLAUDE.md", "규칙\n" * 250)
        _, _, _, data = self.start()
        self.assertIn("CLAUDE.md 250줄", data.get("systemMessage", ""))
        self.assertIn("/harness-core:slim", data["systemMessage"])
        self.assertNotIn("CLAUDE.md", self.start()[3].get("systemMessage", ""), "같은 상태면 다시 알리지 않는다")
        self.write("CLAUDE.md", "규칙\n" * 260)
        self.assertIn("260줄", self.start()[3].get("systemMessage", ""))

    def test_harness_section_is_short(self):
        tpl = (script(CORE, "session_start.py").parent.parent / "templates/claude-md-section.md").read_text()
        self.assertLessEqual(len(tpl.splitlines()), 30, "매 대화에 실리는 구역이라 짧게 유지한다")

    def test_uninitialized_small_repo_silent(self):
        self.git_init()
        self.make_sources(3)
        self.assertEqual(self.start()[1], "")

    def test_uninitialized_big_repo_suggests_init_once(self):
        self.git_init()
        self.make_sources(35)
        ctx = self.context(self.start()[3])
        self.assertIn("/harness-core:init", ctx)
        self.assertFalse((self.proj / "harness.config.json").exists())

    def test_auto_init_creates_config(self):
        self.git_init()
        self.make_sources(35)
        (self.home / ".claude").mkdir()
        (self.home / ".claude" / "harness.config.json").write_text(json.dumps({"auto_init": True}))
        _, _, _, data = self.start()
        self.assertTrue((self.proj / "harness.config.json").exists())
        self.assertIn("auto_init", data.get("systemMessage", ""))

    def test_non_git_dir_silent(self):
        self.make_sources(50)
        self.assertEqual(self.start()[1], "")


class CodemapRefresh(HookCase):
    def test_generates_map_for_initialized_project(self):
        self.config()
        self.write("src/svc.py", "import os\nfrom .db import conn\n\nclass Repo:\n    def find(self):\n        pass\n")
        self.write("web/api.ts", "import { x } from './util'\nexport function getUser() {}\n")
        self.run_hook(CORE, "codemap_refresh.py", {"hook_event_name": "Stop"})
        text = (self.proj / "docs" / "codemap.md").read_text(encoding="utf-8")
        self.assertIn("class Repo — find", text)
        self.assertIn("function getUser", text)

    def test_disabled_or_uninitialized_does_nothing(self):
        self.write("src/svc.py", "def a():\n    pass\n")
        self.run_hook(CORE, "codemap_refresh.py", {"hook_event_name": "Stop"})
        self.assertFalse((self.proj / "docs" / "codemap.md").exists())
        self.config(codemap={"enabled": False})
        self.run_hook(CORE, "codemap_refresh.py", {"hook_event_name": "Stop"})
        self.assertFalse((self.proj / "docs" / "codemap.md").exists())


@unittest.skipUnless(shutil.which("git"), "git 필요")
class Backpressure(HookCase):
    def stop(self, active=False):
        return self.run_hook(FULL, "backpressure.py", {"hook_event_name": "Stop", "stop_hook_active": active})

    def test_failure_blocks_stop(self):
        self.git_init()
        self.config(verify={"test": "echo '1 failed' && exit 1"})
        _, _, _, data = self.stop()
        self.assertEqual(data["decision"], "block")
        self.assertIn("1 failed", data["reason"])

    def test_gives_up_after_three_blocks(self):
        self.git_init()
        self.config(verify={"test": "exit 1"})
        self.assertEqual(self.stop()[3]["decision"], "block")
        self.assertEqual(self.stop(True)[3]["decision"], "block")
        self.assertEqual(self.stop(True)[3]["decision"], "block")
        _, _, _, data = self.stop(True)
        self.assertNotIn("decision", data)
        self.assertIn("3번", data["systemMessage"])

    def test_pass_is_silent_and_cached(self):
        self.git_init()
        marker = self.proj / "runs.txt"
        self.config(verify={"test": f"echo run >> {marker}"})
        self.assertEqual(self.stop()[1], "")
        self.assertEqual(self.stop()[1], "")
        self.assertEqual(marker.read_text().count("run"), 1, "변경이 없으면 다시 돌리지 않아야 함")
        self.write("src/new.py", "x = 1\n")
        self.stop()
        self.assertEqual(marker.read_text().count("run"), 2)

    def test_can_be_disabled(self):
        self.git_init()
        self.config(verify={"test": "exit 1"}, backpressure={"enabled": False})
        self.assertEqual(self.stop()[1], "")


class InitProject(HookCase):
    def init(self, *args):
        return self.run_script(CORE, "init_project.py", "--project", str(self.proj), "--json", *args)

    def test_fresh_project(self):
        self.git_init()
        report = json.loads(self.init().stdout)
        for rel in ("harness.config.json", "CLAUDE.md", "CONTEXT.md", "docs/lessons-learned.md",
                    "docs/error-log.md", "docs/adr/.gitkeep"):
            self.assertTrue((self.proj / rel).exists(), rel)
        self.assertIn(".env", (self.proj / ".gitignore").read_text())
        self.assertTrue(report["actions"])

    def test_idempotent(self):
        self.init()
        self.assertEqual(json.loads(self.init().stdout)["actions"], [])

    def test_dry_run_writes_nothing(self):
        self.init("--dry-run")
        self.assertEqual(list(self.proj.iterdir()), [])

    def test_keeps_user_claude_md_and_updates_section(self):
        self.write("CLAUDE.md", "# 내 앱\n\n직접 쓴 규칙\n")
        self.init()
        text = (self.proj / "CLAUDE.md").read_text()
        self.assertIn("직접 쓴 규칙", text)
        self.assertEqual(text.count("harness:begin"), 1)
        broken = text.replace("## 하네스 규칙", "## 손으로 바꾼 제목")
        (self.proj / "CLAUDE.md").write_text(broken)
        self.init()
        text = (self.proj / "CLAUDE.md").read_text()
        self.assertIn("## 하네스 규칙", text)
        self.assertIn("직접 쓴 규칙", text)

    def test_migrates_v1(self):
        self.write("harness.config.json", json.dumps({"profile": "full", "drift_guard": {"mode": "warn"}}))
        self.write(".claude/verify.json", json.dumps({"lint": "ruff check ."}))
        self.write(".claude/hooks/security_gate.py", "# v1")
        self.write(".claudeignore", ".env\n")
        report = json.loads(self.init().stdout)
        cfg = json.loads((self.proj / "harness.config.json").read_text())
        self.assertNotIn("profile", cfg)
        self.assertEqual(cfg["version"], 2)
        self.assertEqual(cfg["drift_guard"]["mode"], "warn")
        self.assertEqual(cfg["verify"]["lint"], "ruff check .")
        notes = " ".join(report["notes"])
        self.assertIn("v1 훅", notes)
        self.assertIn(".claudeignore", notes)

    def test_shared_lessons_seed(self):
        (self.home / ".claude").mkdir()
        (self.home / ".claude" / "harness-lessons.md").write_text("# 공통 교훈\nL1 — 공유됨\n")
        self.init()
        self.assertIn("공유됨", (self.proj / "docs" / "lessons-learned.md").read_text())


class AuditReport(HookCase):
    def test_summarizes_project_events(self):
        line = {"ts": "2099-01-01T00:00:00", "project": str(self.proj), "hook": "bash_gate",
                "result": "deny", "target": "cat .env", "reason": "시크릿"}
        (self.data / "audit.jsonl").write_text(json.dumps(line, ensure_ascii=False) + "\n")
        out = self.run_script(CORE, "audit_report.py", "--data", str(self.data), "--project", str(self.proj)).stdout
        self.assertIn("bash_gate", out)
        self.assertIn("cat .env", out)


if __name__ == "__main__":
    unittest.main()


class ClaudeMdAudit(HookCase):
    def audit(self):
        import subprocess, sys
        p = subprocess.run([sys.executable, str(script(CORE, "claude_md_audit.py")), "--project", str(self.proj)],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_classifies_blocks_and_skips_harness_section(self):
        self.write("CLAUDE.md", "\n".join([
            "# 프로젝트", "TypeScript strict. 함수는 작게.",
            "## 금지", "- .env 파일은 절대 읽지 마라", "- 강제 푸시 금지",
            "## 운영 규칙", "- 운영 DB에는 절대 직접 쓰지 마라",
            "## 배포 절차", "1. npm run build", "2. npm run test", "3. ./deploy.sh prod", "4. 슬랙에 알림",
            "## API 목록", *[f"| GET | /api/v1/r{i} | 설명 |" for i in range(6)],
            "<!-- harness:begin — x -->", "## 하네스 규칙", "- 무언가", "<!-- harness:end -->",
        ]) + "\n")
        out = self.audit()
        guess = {b["heading"]: (b["guess"], b["covered"]) for b in out["blocks"]}
        self.assertEqual(guess["프로젝트"], ("keep", False))
        self.assertEqual(guess["금지"], ("enforce", True), "하네스가 이미 막는 규칙")
        self.assertEqual(guess["운영 규칙"], ("enforce", False))
        self.assertEqual(guess["배포 절차"][0], "skill")
        self.assertEqual(guess["API 목록"][0], "reference")
        self.assertNotIn("하네스 규칙", guess, "하네스 관리 구역은 분류하지 않는다")
        self.assertEqual(out["files"][0]["harness_section_lines"], 4)
        self.assertLess(out["estimated_after"], out["total_lines"])

    def test_no_claude_md(self):
        out = self.audit()
        self.assertEqual((out["files"], out["blocks"]), ([], []))
