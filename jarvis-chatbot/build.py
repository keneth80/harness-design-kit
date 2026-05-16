"""PyInstaller --onefile 빌드 스크립트.

사용법:
    pip install pyinstaller
    python build.py [--clean]

결과물:
    dist/jarvis  (Mac/Linux)
    dist/jarvis.exe  (Windows)

주의:
    sentence-transformers 가중치는 첫 실행 시 ~/.cache/huggingface 로 다운로드된다.
    오프라인 배포가 필요하면 PyInstaller datas 로 모델 폴더를 포함시켜야 한다.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).parent
ENTRY = ROOT / "src" / "main.py"
STATIC = ROOT / "src" / "dashboard" / "static"
SITE_PACKAGES = Path(sysconfig.get_paths()["purelib"])
# Source-walking 패키지들은 _MEIPASS에 실제 .py 파일이 있어야 한다.
SOURCE_WALK_PACKAGES = ("transformers", "sentence_transformers", "tokenizers", "chromadb")

HIDDEN_IMPORTS = [
    "chromadb",
    "chromadb.api",
    "chromadb.config",
    "chromadb.utils.embedding_functions",
    "sentence_transformers",
    "torch",
    "transformers",
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
    "langgraph",
    "langgraph.checkpoint.memory",
    "langchain_text_splitters",
    "telegram",
    "telegram.ext",
    "fastapi",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "sse_starlette",
    "loguru",
]


def build(clean: bool) -> None:
    if clean:
        for p in (ROOT / "build", ROOT / "dist"):
            if p.exists():
                print(f"clean: rm -rf {p}")
                shutil.rmtree(p)
        for spec in ROOT.glob("*.spec"):
            spec.unlink()

    sep = ";" if sys.platform.startswith("win") else ":"
    args: list[str] = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "jarvis",
        "--paths", str(ROOT),
        "--add-data", f"{STATIC}{sep}src/dashboard/static",
    ]
    # source-walking 패키지: 디렉토리째 _MEIPASS로 추출
    for pkg in SOURCE_WALK_PACKAGES:
        pkg_dir = SITE_PACKAGES / pkg
        if pkg_dir.exists():
            args.extend(["--add-data", f"{pkg_dir}{sep}{pkg}"])
        else:
            print(f"WARN: source dir not found for {pkg}: {pkg_dir}")
        args.extend(["--copy-metadata", pkg])
        args.extend(["--collect-submodules", pkg])
    for hi in HIDDEN_IMPORTS:
        args.extend(["--hidden-import", hi])
    args.append(str(ENTRY))

    print("running:", " ".join(args))
    subprocess.run(args, check=True, cwd=ROOT)
    print("\n빌드 완료 → dist/jarvis")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--clean", action="store_true", help="build/, dist/, *.spec 제거 후 빌드")
    args = p.parse_args()
    build(args.clean)


if __name__ == "__main__":
    main()
