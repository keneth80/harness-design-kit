"""동적 워크플로우 스크립트 흐름 테스트 (가짜 agent()로 실행).

실제 에이전트를 띄우지 않고, 응답 시나리오를 주입해 분기·반복·집계·중단 조건이 맞는지 본다.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = Path(__file__).resolve().parent / "workflow_runner.mjs"
WF = {
    "full-cycle": ROOT / "plugins/harness-full/workflows/full-cycle.js",
    "fix-until-green": ROOT / "plugins/harness-full/workflows/fix-until-green.js",
    "domain-sweep": ROOT / "plugins/harness-full/workflows/domain-sweep.js",
    "design-polish": ROOT / "plugins/harness-design/workflows/design-polish.js",
}


def run(name, args=None, responses=()):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"args": args, "responses": list(responses)}, f, ensure_ascii=False)
    proc = subprocess.run(["node", str(RUNNER), str(WF[name]), f.name], capture_output=True, text=True, timeout=30)
    Path(f.name).unlink()
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    return json.loads(proc.stdout)


def labels(out):
    return [c["label"] for c in out["calls"]]


@unittest.skipUnless(shutil.which("node"), "node 필요")
class FullCycle(unittest.TestCase):
    def ctx(self, **over):
        base = {"hasSpec": True, "architectDone": False, "testsDone": False, "completed": [],
                "features": [{"id": "F1", "title": "로그인", "layers": ["backend", "frontend"]},
                             {"id": "F2", "title": "설정", "layers": ["frontend"]}]}
        base.update(over)
        return {"match": "^context$", "reply": base}

    def test_stops_without_spec(self):
        out = run("full-cycle", responses=[self.ctx(hasSpec=False)])
        self.assertIn("plan-start", out["result"]["stopped"])
        self.assertEqual(labels(out), ["context"])

    def test_stops_when_scaffold_fails(self):
        out = run("full-cycle", responses=[self.ctx(), {"match": "^architect$", "reply": {"ok": False}}])
        self.assertIn("빌드", out["result"]["stopped"])
        self.assertNotIn("F1:backend", labels(out))

    def test_happy_path_order_and_agents(self):
        out = run("full-cycle", responses=[
            self.ctx(),
            {"match": "^architect$", "reply": {"ok": True}},
            {"match": "boundary", "reply": {"high": [{"owner": "frontend", "issue": "camelCase 불일치"}]}},
            {"match": "verify", "reply": {"passed": True, "failures": []}},
        ])
        seq = labels(out)
        self.assertEqual(seq[:3], ["context", "architect", "qa-tester"])
        self.assertLess(seq.index("F1:boundary"), seq.index("F2:frontend"), "기능은 순서대로 하나씩 만든다")
        self.assertIn("F1:fix:frontend", seq)
        self.assertNotIn("F1:fix:backend", seq)
        self.assertNotIn("F2:boundary", seq, "프론트만 있는 기능은 경계 검증이 없다")
        types = {c["label"]: c["agentType"] for c in out["calls"]}
        self.assertEqual(types["architect"], "harness-full:architect")
        self.assertEqual(types["F1:backend"], "harness-full:backend-dev")
        self.assertEqual(types["F1:verify"], "harness-core:code-verifier")
        self.assertTrue(out["result"]["allVerified"])

    def test_resume_skips_done_work_and_filters_features(self):
        out = run("full-cycle", args={"features": ["F2"]}, responses=[
            self.ctx(architectDone=True, testsDone=True),
            {"match": "verify", "reply": {"passed": True}},
        ])
        seq = labels(out)
        self.assertNotIn("architect", seq)
        self.assertNotIn("qa-tester", seq)
        self.assertNotIn("F1:backend", seq)
        self.assertIn("F2:frontend", seq)


@unittest.skipUnless(shutil.which("node"), "node 필요")
class FixUntilGreen(unittest.TestCase):
    def fails(self, n, file="a.ts"):
        return {"passed": False, "failures": [{"file": f"{file}{i % 2}", "message": f"e{i}"} for i in range(n)]}

    def test_passes_after_fixing(self):
        out = run("fix-until-green", args={"command": "npm test"}, responses=[
            {"match": "^check", "reply": [self.fails(3), {"passed": True, "failures": []}]},
        ])
        self.assertTrue(out["result"]["passed"])
        self.assertEqual([r["failures"] for r in out["result"]["rounds"]], [3, 0])
        fixers = [c for c in out["calls"] if c["label"].startswith("fix:")]
        self.assertEqual(len(fixers), 2, "같은 파일의 실패는 한 에이전트가 맡는다")

    def test_stops_when_no_progress_twice(self):
        out = run("fix-until-green", responses=[{"match": "^check", "reply": [self.fails(4), self.fails(4), self.fails(5)]}])
        self.assertFalse(out["result"]["passed"])
        self.assertIn("두 라운드 연속", out["result"]["stopped"])
        self.assertEqual(len(out["result"]["rounds"]), 3)

    def test_round_cap(self):
        replies = [self.fails(10 - i) for i in range(10)]
        out = run("fix-until-green", args={"maxRounds": 3}, responses=[{"match": "^check", "reply": replies}])
        self.assertIn("최대 3라운드", out["result"]["stopped"])


@unittest.skipUnless(shutil.which("node"), "node 필요")
class DomainSweep(unittest.TestCase):
    def test_only_verified_violations_counted(self):
        out = run("domain-sweep", responses=[
            {"match": "^discover$", "reply": {"domains": [
                {"name": "auth", "manual": "docs/domains/auth/manual.md", "codePaths": ["src/auth/**"]},
                {"name": "empty", "manual": "docs/domains/empty/manual.md", "codePaths": []},
            ]}},
            {"match": "^diagnose:auth$", "reply": {"violations": [
                {"rule": "토큰은 auth만 발급", "file": "src/billing/x.ts", "evidence": "sign()", "severity": "high"},
                {"rule": "세션 만료 30분", "file": "src/auth/s.ts", "evidence": "60*60", "severity": "medium"},
            ]}},
            {"match": "^verify:auth$", "reply": [{"isReal": True, "reason": "확인"}, {"isReal": False, "reason": "설정값"}]},
            {"match": "^report$", "reply": {"path": "docs/reviews/domain-sweep-2026-10-28.md"}},
        ])
        r = out["result"]
        self.assertEqual(r["domains"], ["auth"], "code_paths 없는 도메인은 건너뛴다")
        self.assertEqual((r["candidates"], r["confirmed"]), (2, 1))
        self.assertEqual(r["bySeverity"]["high"], 1)

    def test_nothing_to_sweep(self):
        out = run("domain-sweep", responses=[{"match": "^discover$", "reply": {"domains": []}}])
        self.assertIn("없습니다", out["result"]["stopped"])


@unittest.skipUnless(shutil.which("node"), "node 필요")
class DesignPolish(unittest.TestCase):
    DIRS = {"briefFound": True, "directions": [
        {"slug": "calm", "name": "차분", "idea": "i", "layout": "l", "typography": "t", "color": "c"},
        {"slug": "bold", "name": "과감", "idea": "i", "layout": "l", "typography": "t", "color": "c"},
        {"slug": "warm", "name": "따뜻", "idea": "i", "layout": "l", "typography": "t", "color": "c"},
    ]}

    def mock(self, slug):
        return {"slug": slug, "file": f"docs/design/variants/{slug}.html",
                "screenshots": [f"docs/design/variants/shots/{slug}-desktop-light.png"], "summary": {"contrastIssues": 0}}

    def judges(self, a, b, c):
        return {"scores": [{"code": "A", "score": a, "reason": ""}, {"code": "B", "score": b, "reason": ""},
                           {"code": "C", "score": c, "reason": ""}]}

    def base(self):
        return [
            {"match": "^directions$", "reply": self.DIRS},
            {"match": "^mockup:calm$", "reply": self.mock("calm")},
            {"match": "^mockup:bold$", "reply": self.mock("bold")},
            {"match": "^mockup:warm$", "reply": self.mock("warm")},
            {"match": "^judge:brand$", "reply": self.judges(6, 9, 5)},
            {"match": "^judge:usability$", "reply": self.judges(8, 7, 5)},
            {"match": "^judge:craft$", "reply": self.judges(7, 8, 6)},
        ]

    def test_winner_by_total_and_refine_until_pass(self):
        out = run("design-polish", args={"target": "랜딩"}, responses=self.base() + [
            {"match": "^review:r", "reply": [{"pass": False, "average": 3.6, "fixes": ["a", "b", "c"]},
                                             {"pass": True, "average": 4.3, "fixes": []}]},
            {"match": "^fix:r", "reply": self.mock("bold")},
        ])
        r = out["result"]
        self.assertEqual(r["ranking"][0]["slug"], "bold")
        self.assertEqual(r["ranking"][0]["total"], 24)
        self.assertEqual([h["pass"] for h in r["refineHistory"]], [False, True])
        critic_calls = [c for c in out["calls"] if c["label"].startswith(("judge:", "review:"))]
        self.assertTrue(all(c["agentType"] == "harness-design:design-critic" for c in critic_calls))

    def test_final_review_after_last_fix(self):
        out = run("design-polish", args={"rounds": 1}, responses=self.base() + [
            {"match": "^review:r1$", "reply": {"pass": False, "average": 3.4, "fixes": ["a"]}},
            {"match": "^fix:r1$", "reply": self.mock("bold")},
            {"match": "^review:final$", "reply": {"pass": True, "average": 4.1, "fixes": []}},
        ])
        hist = out["result"]["refineHistory"]
        self.assertEqual([h["round"] for h in hist], [1, "final"])
        self.assertTrue(hist[-1]["pass"])

    def test_judges_see_codes_not_names(self):
        # 심사위원 프롬프트에 방향 이름이 들어가지 않는지(블라인드)는 스크립트에서 확인한다
        src = WF["design-polish"].read_text(encoding="utf-8")
        judge_block = src[src.index("const verdicts"):src.index("const totals")]
        self.assertNotIn("d.name", judge_block)
        self.assertNotIn(".slug", judge_block)

    def test_stops_with_fewer_than_two_mockups(self):
        out = run("design-polish", responses=[
            {"match": "^directions$", "reply": self.DIRS},
            {"match": "^mockup:calm$", "reply": self.mock("calm")},
        ])
        self.assertIn("2개 미만", out["result"]["stopped"])


class Meta(unittest.TestCase):
    def test_meta_matches_file_and_phases(self):
        for name, path in WF.items():
            src = path.read_text(encoding="utf-8")
            with self.subTest(workflow=name):
                self.assertTrue(src.startswith("export const meta = {"))
                self.assertIn(f"name: '{name}'", src)
                titles = re.findall(r"\{ title: '([^']+)'", src.split("}\n", 1)[0] + "}")
                used = set(re.findall(r"phase\('([^']+)'\)", src)) | set(re.findall(r"phase: '([^']+)'", src))
                self.assertTrue(used <= set(titles), f"meta.phases에 없는 phase: {used - set(titles)}")
                self.assertNotRegex(src, r"Date\.now\(|Math\.random\(|new Date\(\)|import\(")


if __name__ == "__main__":
    unittest.main()
