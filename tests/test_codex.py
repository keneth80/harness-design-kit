"""harness-codex 테스트: design_only_gate, export_agents."""
import json
import unittest

from helpers import HookCase

P = "harness-codex"

MANUAL = """# rec 도메인 매뉴얼

```yaml
domain: rec
interview_status: complete
last_synced: 2026-10-01   # 마지막 동기화
code_paths:                  # 구현 경로
  - src/domains/rec/**
  - packages/shared/rec.ts
```

## 1. 책임 범위 <!-- src: intent -->
추천 목록 생성만 책임진다.

## 2. 핵심 모델 <!-- src: data_model -->
| Recommendation | userId, items[] |

## 3. 불변 규칙 <!-- src: decisions -->
- 피부톤 최종 값은 skin_profile만 소유한다.

## 4. 의존하는 외부 계약 <!-- src: boundaries -->
- rec ← skin_profile, catalog. 단방향.

## 5. 결정과 근거 <!-- src: decisions -->
| 결정 | 근거 | 문제 |
| 카탈로그 분리 | 신뢰성 | 오염 |

## 6. 알려진 함정 <!-- src: open_questions -->
비밀스러운 함정 메모

## 7. 미해결 항목 <!-- src: open_questions -->
아직 정해지지 않아 구현 전 확정이 필요한 것. 비어 있어야 이상적.
"""


class DesignOnlyGate(HookCase):
    def verdict(self, event):
        return self.decision(self.run_hook(P, "design_only_gate.py", event)[3])

    def test_code_writes_denied(self):
        for path in ["src/app.ts", "backend/main.py", "package.json"]:
            with self.subTest(path=path):
                self.assertEqual(self.verdict(self.tool("Write", file_path=path, content="x")), "deny")

    def test_design_artifacts_allowed(self):
        for path in ["docs/domains/rec/manual.md", "README.md", "src/domains/rec/AGENTS.override.md",
                     "harness.config.json", "/tmp/scratch.py"]:
            with self.subTest(path=path):
                self.assertEqual(self.verdict(self.tool("Edit", file_path=path, old_string="a", new_string="b")), "pass")

    def test_bash_redirect_into_code_denied(self):
        self.assertEqual(self.verdict(self.bash("echo 'x' > src/app.ts")), "deny")
        self.assertEqual(self.verdict(self.bash("cat notes | tee src/x.py")), "deny")
        self.assertEqual(self.verdict(self.bash("npm test 2>&1 > /dev/null")), "pass")
        self.assertEqual(self.verdict(self.bash("git diff > docs/reviews/diff.md")), "pass")

    def test_design_paths_configurable(self):
        self.config(codex={"design_paths": ["docs/**", "contracts/**"]})
        self.assertEqual(self.verdict(self.tool("Write", file_path="contracts/api.ts", content="x")), "pass")
        self.assertEqual(self.verdict(self.tool("Write", file_path="README.md", content="x")), "deny")


class ExportAgents(HookCase):
    def setup_domain(self, status="complete", manual=MANUAL):
        self.write("docs/domains/rec/manual.md", manual)
        self.write("docs/domains/rec/interview.json", json.dumps({"status": status}))

    def export(self, *args):
        r = self.run_script(P, "export_agents.py", "--project", str(self.proj), *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_writes_override_per_code_path(self):
        self.setup_domain()
        report = self.export()
        self.assertEqual(sorted(report["written"]),
                         ["packages/shared/AGENTS.override.md", "src/domains/rec/AGENTS.override.md"])
        text = (self.proj / "src/domains/rec/AGENTS.override.md").read_text(encoding="utf-8")
        self.assertIn("skin_profile만 소유", text)
        self.assertIn("공통 코딩 규칙", text)
        self.assertNotIn("비밀스러운 함정", text, "§6은 내보내지 않는다")
        self.assertNotIn("카탈로그 분리", text, "§5는 내보내지 않는다")
        self.assertIn("synced: 2026-10-01 ·", text, "메타 주석이 값에 섞이면 안 된다")

    def test_incomplete_interview_skipped(self):
        self.setup_domain(status="in_progress")
        report = self.export()
        self.assertEqual(report["written"], [])
        self.assertIn("complete가 아님", report["skipped"][0])

    def test_unresolved_items_block_export(self):
        self.setup_domain(manual=MANUAL.replace("비어 있어야 이상적.", "비어 있어야 이상적.\n- 결제 실패 시 재시도 정책?"))
        report = self.export()
        self.assertEqual(report["written"], [])
        self.assertIn("§7", report["skipped"][0])

    def test_dry_run(self):
        self.setup_domain()
        self.assertTrue(self.export("--dry-run")["written"])
        self.assertFalse((self.proj / "src/domains/rec/AGENTS.override.md").exists())


if __name__ == "__main__":
    unittest.main()
