"""벤치마크 둘러보기(bench_crawl.mjs): 공개 페이지만, robots.txt, 상태 바꾸는 주소 건너뛰기, 폼은 구조만, API 패턴."""
import http.server
import json
import shutil
import subprocess
import threading

from helpers import ROOT, HookCase, need, script

FULL = "harness-full"
NAV = '<nav><a href="/">홈</a><a href="/pricing">요금</a><a href="/about#team">소개</a><a href="/private/admin">관리</a>' \
      '<a href="/logout">로그아웃</a><a href="/pricing?sort=asc">정렬</a><a href="https://other.example/x">외부</a></nav>'
PAGES = {
    "/": f"""<html lang="ko"><head><title>메모 서비스</title><meta name="description" content="빠른 메모"></head><body>{NAV}
<main><h1>생각을 바로 적으세요</h1><h2>세 가지 장점</h2><button>무료로 시작하기</button>
<form action="/signup" method="post"><label for="e">이메일</label><input id="e" name="email" type="email" required value="secret@x.com">
<input type="password" name="pw" value="hunter2"><input type="hidden" name="csrf" value="tok"></form>
<script>fetch('/api/items/123').catch(()=>{{}}); fetch('/api/items/456').catch(()=>{{}})</script></main></body></html>""",
    "/pricing": f"<html><head><title>요금</title></head><body>{NAV}<main><h1>요금제</h1><a class='btn' href='/'>시작</a></main></body></html>",
    "/about": f"<html><head><title>소개</title></head><body>{NAV}<main><h1>팀</h1></main></body></html>",
    "/private/admin": "<html><body>비공개</body></html>",
    "/logout": "<html><body>로그아웃됨</body></html>",
    "/robots.txt": "User-agent: *\nDisallow: /private/\n",
    "/api/items/123": '{"ok":true}', "/api/items/456": '{"ok":true}',
}


class Handler(http.server.BaseHTTPRequestHandler):
    hits = []

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        Handler.hits.append(path)
        body = PAGES.get(path)
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "text/plain" if path == "/robots.txt" else "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write((body or "없음").encode())

    def log_message(self, *a):
        pass


def playwright_ok():
    return shutil.which("node") and subprocess.run(["node", "-e", "require('playwright')"], capture_output=True,
                                                   cwd=str(ROOT)).returncode == 0


@need("playwright", playwright_ok())
class Crawl(HookCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def crawl(self, *args):
        Handler.hits = []
        p = subprocess.run(["node", str(script(FULL, "bench_crawl.mjs")), "--url", self.url + "/", "--delay", "500",
                            "--shots", "1", *args], capture_output=True, text=True, timeout=180, cwd=self.proj,
                           env=self.env(NO_PROXY="127.0.0.1", no_proxy="127.0.0.1"))
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        site_dir = self.proj / out["sites"][0]["dir"]
        return out, json.loads((site_dir / "site.json").read_text()), site_dir

    def test_crawls_public_pages_politely(self):
        out, site, site_dir = self.crawl()
        paths = sorted(p["path"] for p in site["pages"])
        self.assertEqual(paths, ["/", "/about", "/pricing"])
        self.assertNotIn("/private/admin", Handler.hits, "robots.txt 금지 경로는 열지 않는다")
        self.assertNotIn("/logout", Handler.hits, "상태를 바꿀 수 있는 주소는 열지 않는다")
        reasons = {s["url"].split(self.url)[-1]: s["reason"] for s in site["skipped"]}
        self.assertIn("robots", reasons["/private/admin"])
        self.assertTrue(site["robots"]["found"])
        self.assertIn("harness-benchmark", site["userAgent"], "봇임을 숨기지 않는다")

    def test_structure_not_content(self):
        _, site, site_dir = self.crawl()
        home = next(p for p in site["pages"] if p["path"] == "/")
        self.assertEqual(home["title"], "메모 서비스")
        self.assertEqual(home["headings"][0], {"level": 1, "text": "생각을 바로 적으세요"})
        self.assertIn("무료로 시작하기", home["ctas"])
        form = home["forms"][0]
        self.assertEqual((form["action"], form["method"]), ("/signup", "post"))
        self.assertEqual([f["name"] for f in form["fields"]], ["email", "pw"], "hidden 필드는 빼고 구조만")
        self.assertEqual(form["fields"][0]["label"], "이메일")
        dump = json.dumps(site, ensure_ascii=False)
        for value in ("secret@x.com", "hunter2", "tok"):
            self.assertNotIn(value, dump, "입력값은 읽지 않는다")
        self.assertEqual(site["api"].get("GET /api/items/:id"), 2, "API 호출은 id를 지운 패턴으로 센다")
        self.assertTrue((site_dir / "shots/.gitignore").exists(), "남의 화면은 커밋하지 않는다")
        self.assertEqual(len(home.get("shots", [])), 2)

    def test_page_cap(self):
        _, site, _ = self.crawl("--max-pages", "1")
        self.assertEqual(len(site["pages"]), 1)
        self.assertTrue(any("최대 1쪽" in s["reason"] for s in site["skipped"]))


class RobotsRules(HookCase):
    def run_js(self, code):
        p = subprocess.run(["node", "--input-type=module", "-e",
                            f"import * as m from '{script(FULL, 'bench_crawl.mjs').as_uri()}'; {code}"],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    @need("node", shutil.which("node"))
    def test_robots_parsing(self):
        out = self.run_js("""
const txt = `User-agent: Googlebot\\nDisallow: /\\n\\nUser-agent: *\\nDisallow: /search\\nAllow: /search/about\\nDisallow: /*.pdf$\\nCrawl-delay: 3\\n`
const r = m.parseRobots(txt)
console.log(JSON.stringify({delay: r.delay, a: m.robotsAllows(r.rules, '/'), b: m.robotsAllows(r.rules, '/search?q=x'),
  c: m.robotsAllows(r.rules, '/search/about'), d: m.robotsAllows(r.rules, '/doc/a.pdf'),
  own: m.robotsAllows(m.parseRobots('User-agent: harness-benchmark\\nDisallow: /\\n').rules, '/x'),
  id: m.normalizeApiPath('/api/users/42/posts/9f8e7d6c5b4a')}))""")
        self.assertEqual(out, {"delay": 3, "a": True, "b": False, "c": True, "d": False, "own": False,
                               "id": "/api/users/:id/posts/:id"})
