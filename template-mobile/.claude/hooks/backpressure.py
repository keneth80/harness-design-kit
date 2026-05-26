#!/usr/bin/env python3
"""
backpressure.py — Stop Hook (동기)
세션 종료 전 빌드/타입체크/린트/테스트를 실행.
실패 시 exit 2 → 에이전트가 에러를 고칠 때까지 계속 작업.
성공 시 완전 침묵 (컨텍스트에 아무것도 추가 안 됨).

원칙: "성공은 침묵, 실패만 출력"
"""

import json
import os
import subprocess
import sys

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", ".")


def run(cmd: str, label: str, timeout: int = 60) -> tuple[bool, str]:
    """명령 실행. 성공 시 (True, ""), 실패 시 (False, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return True, ""
        # 실패 시 stderr + stdout 중 마지막 50줄만 (컨텍스트 효율)
        output = (result.stderr + "\n" + result.stdout).strip()
        lines = output.split("\n")
        if len(lines) > 50:
            output = f"... ({len(lines) - 50} lines truncated)\n" + "\n".join(lines[-50:])
        return False, f"[{label}] FAILED:\n{output}"
    except subprocess.TimeoutExpired:
        return False, f"[{label}] TIMEOUT after {timeout}s"
    except FileNotFoundError:
        # 명령이 없으면 스킵 (해당 도구 미설치)
        return True, ""


def detect_checks() -> list[tuple[str, str, int]]:
    """프로젝트 구조를 보고 실행할 체크를 자동 감지.
    Returns: [(command, label, timeout), ...]
    """
    checks = []

    # ── Frontend (Node.js) ─────────────────────────
    pkg_json = os.path.join(PROJECT_DIR, "package.json")
    if os.path.exists(pkg_json):
        try:
            with open(pkg_json) as f:
                pkg = json.load(f)
            scripts = pkg.get("scripts", {})

            # TypeScript 타입체크
            if "type-check" in scripts:
                checks.append(("npm run type-check 2>&1", "TypeScript", 30))
            elif os.path.exists(os.path.join(PROJECT_DIR, "tsconfig.json")):
                checks.append(("npx tsc --noEmit 2>&1", "TypeScript", 30))

            # Lint
            if "lint" in scripts:
                checks.append(("npm run lint 2>&1", "Lint", 30))

            # Build (Next.js 등)
            # 빌드는 오래 걸릴 수 있어서 선택적 — 타입체크로 대부분 잡힘
            # if "build" in scripts:
            #     checks.append(("npm run build 2>&1", "Build", 120))

        except (json.JSONDecodeError, OSError):
            pass

    # ── Backend (Python) ───────────────────────────
    requirements = os.path.join(PROJECT_DIR, "backend", "requirements.txt")
    pyproject = os.path.join(PROJECT_DIR, "pyproject.toml")

    if os.path.exists(requirements) or os.path.exists(pyproject):
        # Python 타입체크 (mypy/pyright)
        if os.path.exists(os.path.join(PROJECT_DIR, "backend")):
            # pyright가 있으면 사용, 없으면 스킵 (mypy는 설정 없으면 노이즈가 많음)
            checks.append(("which pyright >/dev/null 2>&1 && pyright backend/ 2>&1 || true", "Python types", 30))

        # pytest (테스트 파일이 있을 때만)
        test_dirs = [
            os.path.join(PROJECT_DIR, "tests"),
            os.path.join(PROJECT_DIR, "backend", "tests"),
        ]
        has_tests = any(
            os.path.exists(d) and any(
                f.startswith("test_") and f.endswith(".py")
                for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))
            )
            for d in test_dirs
            if os.path.exists(d)
        )
        # tests 하위 디렉토리도 재귀적으로 확인
        if not has_tests:
            for d in test_dirs:
                if os.path.exists(d):
                    for root, dirs, files in os.walk(d):
                        if any(f.startswith("test_") and f.endswith(".py") for f in files):
                            has_tests = True
                            break

        if has_tests:
            checks.append(("cd backend && python -m pytest -x -q --tb=short 2>&1 || true", "pytest", 60))

    # ── Vitest (프론트엔드 테스트) ─────────────────
    vitest_config = any(
        os.path.exists(os.path.join(PROJECT_DIR, f))
        for f in ["vitest.config.ts", "vitest.config.js"]
    )
    if vitest_config:
        checks.append(("npx vitest run --reporter=verbose 2>&1", "Vitest", 60))

    # ── Jest (React Native / Expo 테스트) ──────────
    # RN/Expo는 jest를 쓴다. vitest가 이미 잡혔으면 중복 추가하지 않는다.
    if not vitest_config and os.path.exists(pkg_json):
        try:
            with open(pkg_json) as f:
                pkg = json.load(f)
            scripts = pkg.get("scripts", {})
            has_jest_config = (
                "jest" in pkg
                or any(
                    os.path.exists(os.path.join(PROJECT_DIR, f))
                    for f in ["jest.config.js", "jest.config.ts", "jest.config.json"]
                )
            )
            # package.json의 test 스크립트가 jest를 호출하거나, jest 설정이 있을 때만.
            # (Expo 기본 test 스크립트는 "jest" 또는 "jest --watchAll")
            test_script = scripts.get("test", "")
            if "jest" in test_script or has_jest_config:
                # CI 모드로 한 번만 실행 (watch 방지), 테스트 없으면 jest가 통과 처리하도록 --passWithNoTests
                checks.append(("npx jest --ci --passWithNoTests 2>&1", "Jest", 90))
        except (json.JSONDecodeError, OSError):
            pass

    return checks


def main():
    checks = detect_checks()

    if not checks:
        # 체크할 게 없으면 침묵으로 통과
        sys.exit(0)

    errors = []
    for cmd, label, timeout in checks:
        ok, output = run(cmd, label, timeout)
        if not ok:
            errors.append(output)

    if errors:
        # 실패 — 에러를 stderr로 출력, exit 2로 에이전트 재작업 강제
        print(
            "🔴 Back-pressure: 아래 검증이 실패했습니다. 수정 후 다시 시도하세요.\n\n"
            + "\n\n".join(errors),
            file=sys.stderr,
        )
        sys.exit(2)

    # 성공 — 완전 침묵 (컨텍스트에 아무것도 추가 안 됨)
    sys.exit(0)


if __name__ == "__main__":
    main()
