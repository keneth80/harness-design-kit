"""루프 안전장치: 통과 기록 원장(verify_run.py)과 시험지 보호.

- 원장은 스크립트가 직접 돌린 결과만 담고, 서명과 작업 트리 지문으로 변조와 오래됨을 가린다.
- 에이전트는 원장과 서명 키를 쓰거나 읽을 수 없다.
- init한 프로젝트에서는 테스트를 약하게 만드는 변경과 동결 파일 수정이 ask가 된다.
"""
import json
import subprocess
import sys

from helpers import HookCase, script

CORE, FULL = "harness-core", "harness-full"


class LedgerBase(HookCase):
    def setUp(self):
        super().setUp()
        self.git_init()
        self.write(".gitignore", "flag\ncount\n")
        self.commit()

    def commit(self):
        subprocess.run(["git", "add", "-A"], cwd=self.proj, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       cwd=self.proj, check=True)

    def verify(self, *args):
        p = subprocess.run([sys.executable, str(script(CORE, "verify_run.py")), *args], cwd=self.proj,
                           capture_output=True, text=True, timeout=60, env=self.env())
        return p.returncode, json.loads(p.stdout)


class VerifyRun(LedgerBase):
    def test_pass_then_stale_after_edit(self):
        self.config(verify={"lint": "true", "test": "true"})
        self.commit()
        code, out = self.verify()
        self.assertEqual((code, out["state"]), (0, "pass"))
        self.assertEqual([c["name"] for c in out["checks"]], ["lint", "test"])
        self.assertEqual(self.verify("--status")[1]["state"], "pass")
        self.write("src/a.py", "x = 1\n")
        code, st = self.verify("--status")
        self.assertEqual((code, st["state"]), (1, "stale"), "원장 이후 코드가 바뀌면 다시 돌려야 한다")
        self.assertTrue((self.proj / ".harness/.gitignore").exists(), "원장은 커밋되지 않는다")

    def test_harness_outputs_do_not_make_it_stale(self):
        self.config(verify={"test": "true"}, loop={"fingerprint_ignore": ["reports/**"]})
        self.commit()
        self.verify()
        self.write("docs/codemap.md", "# 코드맵\n")          # 세션 종료 때 codemap_refresh가 다시 씀
        self.write("docs/verification-report.md", "# 검증\n")
        self.write("reports/coverage.xml", "<x/>")             # 프로젝트가 지정한 생성물
        self.assertEqual(self.verify("--status")[1]["state"], "pass")
        self.write("saju.py", "x = 1\n")
        self.assertEqual(self.verify("--status")[1]["state"], "stale")

    def test_failure_recorded_with_tail(self):
        self.config(verify={"test": "echo 'assert 1 == 2' && exit 1"})
        code, out = self.verify()
        self.assertEqual((code, out["state"]), (1, "fail"))
        self.assertIn("assert 1 == 2", out["failures"][0]["tail"])

    def test_hand_edited_ledger_is_tampered(self):
        self.config(verify={"test": "exit 1"})
        self.verify()
        path = self.proj / ".harness/verify-ledger.json"
        body = json.loads(path.read_text())
        body["passed"] = True
        body["checks"][0]["exit"] = 0
        path.write_text(json.dumps(body))
        self.assertEqual(self.verify("--status")[1]["state"], "tampered")

    def test_custom_command_is_partial(self):
        self.config(verify={"lint": "true", "test": "true"})
        code, out = self.verify("--cmd", "true")
        self.assertEqual((code, out["state"]), (0, "partial-pass"))
        self.assertEqual(self.verify("--status")[0], 1, "설정된 검사 전부가 아니면 --status는 통과가 아니다")

    def test_changed_config_command_is_not_pass(self):
        self.config(verify={"test": "true"})
        self.verify()
        self.config(verify={"test": "python3 -m pytest"})  # 기준이 바뀌면 예전 원장으로 통과할 수 없다
        self.assertNotEqual(self.verify("--status")[1]["state"], "pass")

    def test_unconfigured(self):
        code, out = self.verify()
        self.assertEqual((code, out["state"]), (2, "unconfigured"))


class LedgerProtection(LedgerBase):
    def key(self):
        return str(self.home / ".claude/harness-data/ledger.key")

    def test_agent_cannot_write_ledger(self):
        self.config()
        ledger = str(self.proj / ".harness/verify-ledger.json")
        _, _, _, d = self.run_hook(CORE, "file_gate.py", self.tool("Write", file_path=ledger, content="{}"))
        self.assertEqual(self.decision(d), "deny")
        for cmd in ("echo '{}' > .harness/verify-ledger.json", "cp x.json .harness/verify-ledger.json",
                    "rm .harness/verify-ledger.json"):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.decision(self.run_hook(CORE, "bash_gate.py", self.bash(cmd))[3]), "deny")

    def test_agent_cannot_read_or_write_key(self):
        self.config()
        for event, tool in ((self.tool("Read", file_path=self.key()), "file_gate.py"),
                            (self.bash(f"cat {self.key()}"), "bash_gate.py"),
                            (self.bash("cat ~/.claude/harness-data/ledger.key"), "bash_gate.py"),
                            (self.bash(f"python3 -c \"print(open('{self.key()}').read())\""), "bash_gate.py"),
                            (self.tool("Write", file_path=self.key(), content="x"), "file_gate.py")):
            with self.subTest(event=str(event)[:80]):
                self.assertEqual(self.decision(self.run_hook(CORE, tool, event)[3]), "deny")

    def test_reading_ledger_is_fine(self):
        self.config()
        ev = self.tool("Read", file_path=str(self.proj / ".harness/verify-ledger.json"))
        self.assertEqual(self.decision(self.run_hook(CORE, "file_gate.py", ev)[3]), "pass")


class BackpressureUsesLedger(LedgerBase):
    def stop(self):
        ev = {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": False}
        return self.run_hook(FULL, "backpressure.py", ev)

    def test_fresh_pass_skips_rerun_and_own_run_writes_ledger(self):
        self.config(verify={"test": "echo run >> count"})
        self.verify()
        runs = (self.proj / "count").read_text().count("run")
        self.assertEqual(self.stop()[0], 0)
        self.assertEqual((self.proj / "count").read_text().count("run"), runs, "원장이 지금 코드 그대로 pass면 다시 돌리지 않는다")

        self.write("src/b.py", "y = 2\n")
        self.stop()
        self.assertEqual((self.proj / "count").read_text().count("run"), runs + 1)
        self.assertEqual(self.verify("--status")[1]["state"], "pass", "backpressure가 돌린 결과도 원장에 남는다")


class TestGuard(HookCase):
    TEST = "tests/test_engine.py"
    BODY = ("def test_ganji():\n    assert ganji(1990) == '경오'\n\n"
            "def test_element():\n    assert element('갑') == '목'\n    assert element('을') == '목'\n")

    def setUp(self):
        super().setUp()
        self.config()  # init한 프로젝트에서만 보호
        self.write(self.TEST, self.BODY)

    def edit(self, old, new, path=None):
        ev = self.tool("Edit", file_path=str(self.proj / (path or self.TEST)), old_string=old, new_string=new)
        return self.run_hook(CORE, "file_gate.py", ev)[3]

    def test_adding_skip_asks(self):
        d = self.edit("def test_ganji():", "@pytest.mark.skip\ndef test_ganji():")
        self.assertEqual(self.decision(d), "ask")
        self.assertIn("skip", d["hookSpecificOutput"]["permissionDecisionReason"])

    def test_removing_assert_or_test_asks(self):
        self.assertEqual(self.decision(self.edit("    assert element('을') == '목'\n", "")), "ask")
        self.assertEqual(self.decision(self.edit(
            "def test_ganji():\n    assert ganji(1990) == '경오'\n\n", "")), "ask")

    def test_strengthening_or_fixing_passes(self):
        self.assertEqual(self.decision(self.edit(
            "    assert element('을') == '목'\n",
            "    assert element('을') == '목'\n    assert element('병') == '화'\n")), "pass")
        self.assertEqual(self.decision(self.edit("ganji(1990) == '경오'", "ganji(1990) == '경오'  # 입춘 기준")), "pass")

    def test_new_test_file_passes_but_weaker_overwrite_asks(self):
        new = self.tool("Write", file_path=str(self.proj / "tests/test_new.py"), content="def test_a():\n    pass\n")
        self.assertEqual(self.decision(self.run_hook(CORE, "file_gate.py", new)[3]), "pass")
        over = self.tool("Write", file_path=str(self.proj / self.TEST), content="def test_ganji():\n    pass\n")
        self.assertEqual(self.decision(self.run_hook(CORE, "file_gate.py", over)[3]), "ask")

    def test_frozen_golden_data_asks_on_any_edit(self):
        self.write("tests/golden/cases.csv", "birth,expected\n1990-01-01,경오\n")
        d = self.edit("경오", "기사", path="tests/golden/cases.csv")
        self.assertEqual(self.decision(d), "ask")
        self.assertIn("동결", d["hookSpecificOutput"]["permissionDecisionReason"])

    def test_shell_delete_or_overwrite_asks(self):
        self.write("tests/golden/cases.csv", "a\n")
        for cmd in (f"rm {self.TEST}", f"git rm {self.TEST}", f"mv {self.TEST} /tmp/x.py",
                    f"echo '' > {self.TEST}", f"sed -i 's/assert/#assert/' {self.TEST}",
                    "cp new.csv tests/golden/cases.csv"):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.decision(self.run_hook(CORE, "bash_gate.py", self.bash(cmd))[3]), "ask")
        self.assertEqual(self.decision(self.run_hook(CORE, "bash_gate.py", self.bash("echo x > tests/test_brand_new.py"))[3]),
                         "pass", "새 테스트 파일을 만드는 것은 막지 않는다")

    def test_js_and_go_markers(self):
        self.write("src/a.test.ts", "it('works', () => {\n  expect(a()).toBe(1)\n})\n")
        d = self.edit("it('works'", "it.skip('works'", path="src/a.test.ts")
        self.assertEqual(self.decision(d), "ask")
        self.write("pkg/a_test.go", "func TestA(t *testing.T) {\n\tif a() != 1 {\n\t\tt.Fatal(\"x\")\n\t}\n}\n")
        self.assertEqual(self.decision(self.edit("func TestA(t *testing.T) {\n", "func TestA(t *testing.T) {\n\tt.Skip()\n",
                                                 path="pkg/a_test.go")), "ask")

    def test_off_when_uninitialized_or_disabled_and_ignores_source(self):
        self.assertEqual(self.decision(self.edit("x", "y", path="src/engine.py")), "pass")
        self.config(loop={"protect_tests": False})
        self.assertEqual(self.decision(self.edit("def test_ganji():", "@pytest.mark.skip\ndef test_ganji():")), "pass")
        (self.proj / "harness.config.json").unlink()
        self.assertEqual(self.decision(self.edit("def test_ganji():", "@pytest.mark.skip\ndef test_ganji():")), "pass")
