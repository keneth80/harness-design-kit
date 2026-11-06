#!/usr/bin/env python3
"""loop_setup: 루프 안전장치를 프로젝트에 맞추기 위한 진단과 적용.

루프가 믿을 두 가지를 정한다.
  1) 검사 명령(verify): 원장이 "통과"를 판단하는 기준
  2) 동결 경로(loop.frozen): 사람이 정한 정답 데이터. 에이전트가 고치면 ask

진단만 하고 아무것도 바꾸지 않는다 (기본):
  python3 loop_setup.py [--project DIR]
사용자 확인 후 적용:
  python3 loop_setup.py --write-verify                 감지한 검사 명령을 verify에 적는다 (verify가 비어 있을 때만)
  python3 loop_setup.py --freeze "data/expected/**"    loop.frozen에 패턴을 더한다 (여러 번 가능)
  python3 loop_setup.py --test-path "src/**/*Spec.scala"  loop.test_paths에 패턴을 더한다

출력은 JSON. 특정 프로젝트·언어에 묶이지 않도록 이름 규칙만으로 후보를 찾는다.
"""
import argparse
import fnmatch
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build",
             "target", "vendor", ".harness", ".next", ".nuxt", "coverage", ".tox", ".mypy_cache",
             ".pytest_cache", ".gradle", ".idea", ".vscode", "out", "bin", "obj"}
# 기대값(정답)을 담는 폴더에 흔히 쓰는 이름. 입력 데이터일 수도 있어 기본값이 아니라 후보로만 낸다
FROZEN_DIR_NAMES = {"golden", "goldens", "expected", "expectations", "baseline", "baselines", "approved",
                    "reference", "references", "oracle", "oracles"}
FROZEN_FILE_PATTERNS = ["*expected*.json", "*expected*.csv", "*expected*.txt", "*expected*.yaml",
                        "*expected*.yml", "*expected*.xml", "*.golden", "*.golden.*", "*.approved.*",
                        "*_snapshot.*", "*.snapshot"]
# 기본 test_paths에 없을 수 있는 테스트 파일 이름 규칙 (언어별)
TEST_FILE_PATTERNS = ["*Test.java", "*Tests.java", "*Test.kt", "*Tests.kt", "*Tests.cs", "*Test.cs",
                      "*_spec.rb", "*Spec.scala", "*Test.php", "*_test.exs", "*Tests.swift", "*_test.dart",
                      "*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go", "*_test.rs"]
MAX_FILES = 20000
MAX_CANDIDATES = 20


def walk(proj):
    count = 0
    for root, dirs, files in os.walk(proj):
        rel_root = os.path.relpath(root, proj)
        depth = 0 if rel_root == "." else rel_root.count(os.sep) + 1
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")] if depth < 7 else []
        yield rel_root, dirs, files
        count += len(files)
        if count > MAX_FILES:
            return


def scan(proj, cfg):
    loop = cfg.get("loop") or {}
    frozen, tests = loop.get("frozen") or [], loop.get("test_paths") or []
    frozen_c, test_c = [], []
    seen = set()
    for rel_root, dirs, files in walk(proj):
        for d in dirs:
            rel = d if rel_root == "." else os.path.join(rel_root, d)
            if d.lower() in FROZEN_DIR_NAMES and not _lib.glob_match(rel + "/x", frozen):
                frozen_c.append({"pattern": rel.replace(os.sep, "/") + "/**",
                                 "reason": f"기대값 폴더에 흔한 이름 ({d})"})
        for f in files:
            rel = (f if rel_root == "." else os.path.join(rel_root, f)).replace(os.sep, "/")
            in_frozen_dir = any(c["pattern"][:-3] in rel for c in frozen_c)
            if not in_frozen_dir and not _lib.glob_match(rel, frozen) and \
                    any(fnmatch.fnmatch(f, p) for p in FROZEN_FILE_PATTERNS):
                frozen_c.append({"pattern": rel, "reason": "기대값 파일에 흔한 이름"})
            for p in TEST_FILE_PATTERNS:
                if fnmatch.fnmatch(f, p) and not _lib.glob_match(rel, tests) and p not in seen:
                    seen.add(p)
                    test_c.append({"pattern": p, "example": rel, "reason": "기본 test_paths에 없는 테스트 파일 이름"})
    return frozen_c[:MAX_CANDIDATES], test_c[:MAX_CANDIDATES]


def diagnose(proj):
    cfg = _lib.load_config(proj)
    configured = {k: v for k, v in (cfg.get("verify") or {}).items() if k in _lib.CHECK_KEYS and v}
    detected = _lib.autodetect_checks(proj)
    frozen_c, test_c = scan(proj, cfg)
    loop = cfg.get("loop") or {}
    return {
        "initialized": _lib.is_initialized(proj),
        "protect_tests": _lib.tests_protected(proj, cfg),
        "verify": {
            "configured": configured or None,
            "detected": detected or None,
            "source": "config" if configured else "autodetect" if detected else "none",
        },
        "frozen": {"configured": loop.get("frozen") or [], "candidates": frozen_c},
        "test_paths": {"candidates": test_c},
        "ledger": _lib.ledger_status(proj, cfg).get("state"),
    }


def apply(proj, write_verify, freeze, test_paths):
    path = os.path.join(proj, _lib.CONFIG_FILE)
    if not os.path.exists(path):
        raise SystemExit("harness.config.json이 없습니다. /harness-core:init을 먼저 실행하세요.")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    changes = []
    if write_verify:
        current = {k: v for k, v in (cfg.get("verify") or {}).items() if k in _lib.CHECK_KEYS and v}
        detected = _lib.autodetect_checks(proj)
        if current:
            changes.append("verify가 이미 있어 그대로 둠")
        elif detected:
            cfg["verify"] = {**(cfg.get("verify") or {}), **detected}
            changes.append(f"verify에 감지한 명령을 적음: {detected}")
        else:
            changes.append("감지한 검사 명령이 없어 verify를 직접 적어야 함")
    loop = cfg.setdefault("loop", {})
    for key, items, default in (("frozen", freeze, _lib.DEFAULT_CONFIG["loop"]["frozen"]),
                                ("test_paths", test_paths, _lib.DEFAULT_CONFIG["loop"]["test_paths"])):
        if not items:
            continue
        # 프로젝트 설정의 목록은 기본값을 대체하므로, 처음 적을 때 기본값을 함께 적는다
        current = list(loop.get(key) or default)
        added = [p for p in items if p not in current]
        loop[key] = current + added
        if added:
            changes.append(f"loop.{key}에 추가: {added}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    ap.add_argument("--write-verify", action="store_true")
    ap.add_argument("--freeze", action="append", default=[])
    ap.add_argument("--test-path", action="append", default=[])
    args = ap.parse_args()
    proj = os.path.abspath(args.project)
    out = {}
    if args.write_verify or args.freeze or args.test_path:
        out["changes"] = apply(proj, args.write_verify, args.freeze, args.test_path)
    out.update(diagnose(proj))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
