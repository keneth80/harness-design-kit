#!/usr/bin/env python3
"""
codemap: 코드를 정적 파싱해 "어디에 무엇이 있고 무엇을 import하는지" 텍스트 지도를 만든다.
docs/codemap.md 로 출력. 세션이 끊겨도 에이전트가 전체 코드를 다 읽지 않고 구조를 파악하게 한다.

가벼운 수준만 담는다:
  - 각 파일이 export하는 공개 함수/클래스/상수 (시그니처)
  - 각 파일이 import하는 모듈
함수 본문의 호출관계나 의미 요약은 담지 않는다(코드와 어긋날 위험·비용 때문).

지원: Python(.py), JS/TS(.js/.jsx/.ts/.tsx)
사용: python3 codemap.py [루트경로]  (기본: 현재 디렉터리)
"""
import sys, os, ast, re, datetime

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist",
             "build", ".next", "coverage", ".claude"}
PY_EXT = {".py"}
JS_EXT = {".js", ".jsx", ".ts", ".tsx"}


def py_summary(path):
    """파이썬 파일에서 공개 def/class와 import를 추출."""
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except Exception as e:
        return None, [f"(파싱 실패: {e})"], []
    exports, imports = [], []
    for node in tree.body:  # 최상위만 (공개 API)
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if node.name.startswith("_"):
                continue
            args = [a.arg for a in node.args.args]
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            exports.append(f"{prefix} {node.name}({', '.join(args)})")
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            methods = [n.name for n in node.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and not n.name.startswith("_")]
            exports.append(f"class {node.name}" + (f" — {', '.join(methods)}" if methods else ""))
        elif isinstance(node, ast.Import):
            imports += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level:  # 상대 import
                mod = "." * node.level + mod
            imports.append(mod)
    return exports, imports, []


def js_summary(path):
    """JS/TS에서 export와 import를 정규식으로 추출(가벼운 근사)."""
    try:
        src = open(path, encoding="utf-8").read()
    except Exception as e:
        return None, [], []
    exports, imports = [], []
    # export function / const / class / default
    for m in re.finditer(r"export\s+(?:default\s+)?(?:async\s+)?(function|const|class|let|var)\s+(\w+)", src):
        exports.append(f"{m.group(1)} {m.group(2)}")
    # export { a, b }
    for m in re.finditer(r"export\s*\{([^}]+)\}", src):
        names = [n.strip().split(" as ")[0].strip() for n in m.group(1).split(",") if n.strip()]
        exports += [f"export {{{n}}}" for n in names]
    # import ... from 'x'
    for m in re.finditer(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", src):
        imports.append(m.group(1))
    return exports, imports, []


def build_map(root):
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            ext = os.path.splitext(fn)[1]
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            if ext in PY_EXT:
                exports, imports, _ = py_summary(full)
            elif ext in JS_EXT:
                exports, imports, _ = js_summary(full)
            else:
                continue
            if exports is None and not imports:
                continue
            # 외부 라이브러리 import는 줄이고, 로컬(상대/프로젝트내) import 위주로.
            # 흔한 외부 패키지를 제외하는 방식으로 로컬을 넓게 잡는다.
            EXTERNAL = {"os","sys","re","json","ast","typing","datetime","pathlib",
                        "collections","functools","itertools","asyncio","logging",
                        "fastapi","pydantic","sqlalchemy","numpy","pandas","requests",
                        "react","express","lodash","axios","next"}
            local_imports = []
            for i in (imports or []):
                top = i.lstrip(".").split(".")[0].split("/")[0]
                if i.startswith(".") or (top and top not in EXTERNAL):
                    local_imports.append(i)
            entries.append((rel, exports or [], local_imports))
    return entries


def render(entries, root):
    today = datetime.date.today().isoformat()
    lines = [
        "# 코드맵 (자동 생성)",
        "",
        "> 이 파일은 codemap.py가 코드를 정적 파싱해 자동 생성합니다. **직접 수정하지 마세요.**",
        "> 코드가 바뀌면 `python3 .claude/hooks/codemap.py` 로 다시 생성하세요.",
        f"> generated: {today} · 파일 {len(entries)}개",
        "",
        "각 파일이 **무엇을 export하고**(공개 API) **어떤 로컬 모듈을 import하는지**의 지도입니다.",
        "함수 본문의 호출관계·의미는 담지 않습니다. 세부는 실제 코드를 보세요.",
        "",
    ]
    # 디렉터리별 묶기
    by_dir = {}
    for rel, exports, imports in entries:
        d = os.path.dirname(rel) or "."
        by_dir.setdefault(d, []).append((rel, exports, imports))
    for d in sorted(by_dir):
        lines.append(f"## {d}/")
        for rel, exports, imports in sorted(by_dir[d]):
            fname = os.path.basename(rel)
            lines.append(f"### {fname}")
            if exports:
                lines.append("- exports: " + "; ".join(exports))
            else:
                lines.append("- exports: (없음/비공개)")
            if imports:
                lines.append("- imports(local): " + ", ".join(sorted(set(imports))))
            lines.append("")
    return "\n".join(lines)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    root = os.path.abspath(root)
    entries = build_map(root)
    if not entries:
        print("코드맵: 파싱할 소스 파일을 찾지 못했습니다.", file=sys.stderr)
        sys.exit(0)
    out_dir = os.path.join(root, "docs")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "codemap.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(entries, root))
    print(f"codemap 생성: {out} (파일 {len(entries)}개)")


if __name__ == "__main__":
    main()
