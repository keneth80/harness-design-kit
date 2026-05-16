# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import copy_metadata

datas = [('/Users/kenneth.kang/kenneth/00.dev/ai-project/harness/harness-kit/jarvis-chatbot/src/dashboard/static', 'src/dashboard/static'), ('/Users/kenneth.kang/kenneth/00.dev/ai-project/harness/harness-kit/jarvis-chatbot/.venv/lib/python3.14/site-packages/transformers', 'transformers'), ('/Users/kenneth.kang/kenneth/00.dev/ai-project/harness/harness-kit/jarvis-chatbot/.venv/lib/python3.14/site-packages/sentence_transformers', 'sentence_transformers'), ('/Users/kenneth.kang/kenneth/00.dev/ai-project/harness/harness-kit/jarvis-chatbot/.venv/lib/python3.14/site-packages/tokenizers', 'tokenizers'), ('/Users/kenneth.kang/kenneth/00.dev/ai-project/harness/harness-kit/jarvis-chatbot/.venv/lib/python3.14/site-packages/chromadb', 'chromadb')]
hiddenimports = ['chromadb', 'chromadb.api', 'chromadb.config', 'chromadb.utils.embedding_functions', 'sentence_transformers', 'torch', 'transformers', 'tiktoken_ext', 'tiktoken_ext.openai_public', 'langgraph', 'langgraph.checkpoint.memory', 'langchain_text_splitters', 'telegram', 'telegram.ext', 'fastapi', 'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'sse_starlette', 'loguru']
datas += copy_metadata('transformers')
datas += copy_metadata('sentence_transformers')
datas += copy_metadata('tokenizers')
datas += copy_metadata('chromadb')
hiddenimports += collect_submodules('transformers')
hiddenimports += collect_submodules('sentence_transformers')
hiddenimports += collect_submodules('tokenizers')
hiddenimports += collect_submodules('chromadb')


a = Analysis(
    ['/Users/kenneth.kang/kenneth/00.dev/ai-project/harness/harness-kit/jarvis-chatbot/src/main.py'],
    pathex=['/Users/kenneth.kang/kenneth/00.dev/ai-project/harness/harness-kit/jarvis-chatbot'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='jarvis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
