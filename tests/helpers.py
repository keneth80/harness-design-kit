"""훅 회귀 테스트 공용 헬퍼.

훅 스크립트를 Claude Code가 하는 방식 그대로 호출한다:
  stdin으로 이벤트 JSON을 주고, exit code / stdout / stderr를 검사.
계약: exit 0=허용(stdout=경고), exit 2=차단(stderr=피드백).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent
UNIVERSAL = KIT_ROOT / "template-universal"
CHATBOT = KIT_ROOT / "template"
HOOKS_DIR = UNIVERSAL / ".claude" / "hooks"


def run_hook(hook_name, event, hooks_dir=HOOKS_DIR, timeout=30, env_extra=None):
    """훅 스크립트에 이벤트를 stdin JSON으로 넘겨 실행. (exit, stdout, stderr) 반환."""
    env = {**os.environ, "HARNESS_MONITOR": ""}  # 모니터 로깅 비활성 고정
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(Path(hooks_dir) / hook_name)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def edit_event(project_dir, file_path, tool_name="Edit"):
    return {
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
        "cwd": str(project_dir),
    }


def make_domain_fixture(project_dir, domain="auth", interview=None,
                        code_paths=("backend/**", "frontend/**"),
                        last_synced="2099-12-31"):
    """docs/domains/<domain>/ 아래 manual.md(+interview.json) 픽스처 생성.

    last_synced 기본값을 먼 미래로 두어 mtime 기반 Drift A/B 경고가
    테스트 대상 판정(차단/강등)에 섞이지 않게 한다.
    """
    project_dir = Path(project_dir)
    domain_dir = project_dir / "docs" / "domains" / domain
    domain_dir.mkdir(parents=True, exist_ok=True)
    paths_yaml = "\n".join(f"  - {p}" for p in code_paths)
    (domain_dir / "manual.md").write_text(
        "```yaml\n"
        f"last_synced: {last_synced}\n"
        "interview_status: n/a\n"
        "code_paths:\n"
        f"{paths_yaml}\n"
        "```\n",
        encoding="utf-8",
    )
    if interview is not None:
        (domain_dir / "interview.json").write_text(
            json.dumps(interview, ensure_ascii=False), encoding="utf-8"
        )
    (project_dir / "backend").mkdir(exist_ok=True)
    (project_dir / "frontend").mkdir(exist_ok=True)
    return domain_dir


def write_config(project_dir, drift_guard=None, profile="lite"):
    cfg = {"profile": profile}
    if drift_guard is not None:
        cfg["drift_guard"] = drift_guard
    (Path(project_dir) / "harness.config.json").write_text(
        json.dumps(cfg, ensure_ascii=False), encoding="utf-8"
    )


def registered_hook_scripts(settings_path):
    """settings.json에 등록된 훅 스크립트 파일명 집합."""
    settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    scripts = set()
    for entries in settings.get("hooks", {}).values():
        for entry in entries:
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                for token in cmd.split():
                    if token.endswith(".py"):
                        scripts.add(os.path.basename(token))
    return scripts
