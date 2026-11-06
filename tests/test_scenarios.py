"""시나리오 검사: needs 순서·blocked, command·http 검사, 환경변수, 위험·복구 확인, 원장 연동, 파일 보호."""
import http.server
import json
import subprocess
import sys
import threading

from helpers import HookCase, script

CORE, FULL = "harness-core", "harness-full"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        routes = {"/": (200, "home ok"), "/health": (200, '{"ok":true}'), "/version": (200, '{"v":"1"}')}
        code, body = routes.get(self.path, (404, "not found"))
        if self.path == "/secure":
            code, body = (200, "secret ok") if self.headers.get("Authorization") == "Bearer t0k" else (401, "no")
        self.send_response(code)
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):
        pass


class ScenarioCase(HookCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def scenarios(self, items):
        self.write("harness.scenarios.json", json.dumps({"scenarios": items}, ensure_ascii=False))

    def run_s(self, *args, **env):
        env = {"BASE_URL": self.url, "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost", **env}
        p = subprocess.run([sys.executable, str(script(CORE, "scenario_run.py")), *args], cwd=self.proj,
                           capture_output=True, text=True, timeout=60, env=self.env(**env))
        return p.returncode, json.loads(p.stdout)

    def by_id(self, out):
        return {r["id"]: r for r in out["results"]}


class Engine(ScenarioCase):
    def test_order_needs_and_blocked(self):
        self.scenarios([
            {"id": "api", "then": "API", "needs": ["server"], "check": {"type": "http", "url": "${BASE_URL}/health",
                                                                      "expect": {"contains": '"ok":true'}}},
            {"id": "server", "then": "서버", "check": {"type": "command", "run": "exit 1"}},
            {"id": "page", "then": "페이지", "check": {"type": "http", "url": "${BASE_URL}/"}},
        ])
        code, out = self.run_s()
        r = self.by_id(out)
        self.assertEqual(code, 1)
        self.assertEqual([x["id"] for x in out["results"]], ["server", "api", "page"], "needs 순서대로 돈다")
        self.assertEqual(r["server"]["status"], "fail")
        self.assertEqual(r["api"]["status"], "blocked")
        self.assertIn("server", r["api"]["reason"])
        self.assertEqual(r["page"]["status"], "pass")

    def test_http_and_command_expectations(self):
        self.scenarios([
            {"id": "404", "then": "없는 주소", "check": {"type": "http", "url": "${BASE_URL}/nope", "expect": {"status": 404}}},
            {"id": "auth", "then": "토큰", "check": {"type": "http", "url": "${BASE_URL}/secure",
                                                  "headers": {"Authorization": "Bearer ${API_TOKEN}"}, "expect": {"contains": "secret"}}},
            {"id": "out", "then": "출력", "check": {"type": "command", "run": "echo up to date", "expect": {"contains": "up to date"}}},
            {"id": "wrong", "then": "틀린 기대", "check": {"type": "http", "url": "${BASE_URL}/", "expect": {"contains": "zzz"}}},
        ])
        code, out = self.run_s(API_TOKEN="t0k")
        r = self.by_id(out)
        self.assertEqual([r[k]["status"] for k in ("404", "auth", "out", "wrong")], ["pass", "pass", "pass", "fail"])
        self.assertNotIn("t0k", json.dumps(out), "헤더 값(토큰)은 출력에 남기지 않는다")

    def test_missing_env_is_skipped_not_pass(self):
        self.scenarios([{"id": "prod", "then": "운영", "check": {"type": "http", "url": "${PROD_URL}/"}}])
        code, out = self.run_s()
        self.assertEqual(code, 1)
        self.assertEqual(out["results"][0]["status"], "skipped")
        self.assertIn("PROD_URL", out["results"][0]["reason"])

    def test_risk_shows_recovery_and_runs_only_checks(self):
        self.scenarios([
            {"id": "home", "then": "홈", "tags": ["deploy"], "check": {"type": "http", "url": "${BASE_URL}/"}},
            {"id": "live", "then": "새 버전", "tags": ["deploy"],
             "check": {"type": "http", "url": "${BASE_URL}/version", "expect": {"contains": '"v":"2"'}},
             "risk": {"impact": "전체 사용자", "recovery": "touch rolled-back 으로 되돌린다", "recoveryChecks": ["home"]}},
        ])
        code, out = self.run_s("--only", "live")
        r = self.by_id(out)
        self.assertEqual(r["live"]["status"], "fail")
        self.assertEqual(r["live"]["risk"]["recoveryChecks"], {"home": "pass"})
        self.assertIn("되돌린다", r["live"]["risk"]["recovery"])
        self.assertFalse((self.proj / "rolled-back").exists(), "복구 방법은 실행하지 않는다")

    def test_tags_select_with_needs(self):
        self.scenarios([
            {"id": "build", "then": "빌드", "check": {"type": "command", "run": "true"}},
            {"id": "home", "then": "홈", "needs": ["build"], "tags": ["local"], "check": {"type": "http", "url": "${BASE_URL}/"}},
            {"id": "prod", "then": "운영", "tags": ["deploy"], "check": {"type": "http", "url": "${PROD_URL}/"}},
        ])
        code, out = self.run_s("--only", "local")
        self.assertEqual(code, 0)
        self.assertEqual([x["id"] for x in out["results"]], ["build", "home"], "태그로 고르면 그 needs도 함께 돈다")

    def test_invalid_files(self):
        for items, needle in (([{"id": "a", "then": "", "needs": ["b"], "check": {"type": "command", "run": "true"}},
                                {"id": "b", "then": "", "needs": ["a"], "check": {"type": "command", "run": "true"}}], "순환"),
                              ([{"id": "a", "then": "", "needs": ["x"], "check": {"type": "command", "run": "true"}}], "없는"),
                              ([{"id": "a", "then": "", "check": {"type": "ftp"}}], "command 또는 http")):
            with self.subTest(needle=needle):
                self.scenarios(items)
                code, out = self.run_s()
                self.assertEqual(code, 2)
                self.assertIn(needle, out["error"])

    def test_template_is_valid(self):
        tpl = (script(CORE, "scenario_run.py").parent.parent / "templates/harness.scenarios.json").read_text()
        self.write("harness.scenarios.json", tpl)
        p = subprocess.run([sys.executable, str(script(CORE, "scenario_run.py")), "--list"], cwd=self.proj,
                           capture_output=True, text=True, env=self.env())
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertEqual([s["id"] for s in json.loads(p.stdout)], ["build", "home", "missing-route", "live"])


class LedgerIntegration(ScenarioCase):
    def setUp(self):
        super().setUp()
        self.git_init()
        self.write(".gitignore", "count\n")

    def verify(self, *args, **env):
        env = {"BASE_URL": self.url, "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost", **env}
        p = subprocess.run([sys.executable, str(script(CORE, "verify_run.py")), *args], cwd=self.proj,
                           capture_output=True, text=True, timeout=60, env=self.env(**env))
        return p.returncode, json.loads(p.stdout)

    def test_scenarios_become_part_of_pass(self):
        self.scenarios([
            {"id": "home", "then": "홈", "tags": ["local"], "check": {"type": "http", "url": "${BASE_URL}/"}},
            {"id": "prod", "then": "운영", "tags": ["deploy"], "check": {"type": "http", "url": "${PROD_URL}/"}},
        ])
        self.config(verify={"test": "true", "scenarios": ["local"]})
        code, out = self.verify()
        self.assertEqual((code, out["state"]), (0, "pass"))
        self.assertIn("scenarios", [c["name"] for c in out["checks"]])

        self.config(verify={"test": "true", "scenarios": True})  # 전부 묶으면 PROD_URL 없는 운영 시나리오 때문에 실패
        code, out = self.verify()
        self.assertEqual((code, out["state"]), (1, "fail"))
        self.assertIn("[skipped] prod", out["failures"][0]["tail"])

    def test_backpressure_runs_scenarios(self):
        self.scenarios([{"id": "broken", "then": "깨진 페이지", "check": {"type": "http", "url": "${BASE_URL}/nope"}}])
        self.config(verify={"scenarios": True})
        ev = {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": False}
        _, _, _, data = self.run_hook(FULL, "backpressure.py", ev, BASE_URL=self.url,
                                      NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
        self.assertEqual(data["decision"], "block")
        self.assertIn("[fail] broken", data["reason"])

    def test_scenario_file_is_protected(self):
        self.config()
        new = self.tool("Write", file_path=str(self.proj / "harness.scenarios.json"), content='{"scenarios": []}')
        self.assertEqual(self.decision(self.run_hook(CORE, "file_gate.py", new)[3]), "pass", "처음 만드는 것은 허용")
        self.scenarios([{"id": "a", "then": "", "check": {"type": "command", "run": "true"}}])
        ev = self.tool("Edit", file_path=str(self.proj / "harness.scenarios.json"), old_string="true", new_string="exit 0")
        self.assertEqual(self.decision(self.run_hook(CORE, "file_gate.py", ev)[3]), "ask")
