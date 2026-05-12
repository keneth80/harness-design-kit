"""LM Studio OpenAI 호환 API 클라이언트 — 검증 Hook 공용 모듈

LM Studio 로컬 서버 (localhost:1234)를 사용.
OpenAI 호환 /v1/chat/completions 엔드포인트 호출.

모델명은 LM Studio에서 로드한 모델 identifier를 사용.
LM Studio GUI > Local Server 탭에서 확인 가능.
"""

import json
import re
import sys
import requests
from typing import Optional

# ── 설정 ──────────────────────────────────────────────
# LM Studio 기본 포트: 1234
# 모델명: LM Studio 서버 패널에 표시된 identifier 사용
#   예: "qwen3-8b", "lmstudio-community/qwen3-8B-GGUF" 등
#   여러 모델 로드 시 정확한 identifier 필요, 단일 모델이면 아무 값이나 OK
LMSTUDIO_BASE_URL = "http://localhost:1234"
DEFAULT_MODEL = "qwen3-8b"
TIMEOUT_SECONDS = 25

def ask(
    prompt: str, system: str = "", model: str = DEFAULT_MODEL,
    temperature: float = 0.1, max_tokens: int = 1024, json_mode: bool = False,
) -> Optional[str]:
    """LM Studio /v1/chat/completions 호출."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        resp = requests.post(
            f"{LMSTUDIO_BASE_URL}/v1/chat/completions",
            json=payload, timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.Timeout:
        return None
    except (requests.RequestException, KeyError, IndexError) as e:
        print(f"[llm_client] LM Studio error: {e}", file=sys.stderr)
        return None

def ask_json(prompt: str, system: str = "", model: str = DEFAULT_MODEL) -> Optional[dict]:
    """JSON 응답을 파싱해서 dict로 반환."""
    raw = ask(prompt, system, model, json_mode=True)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try: return json.loads(m.group())
            except: pass
        return None

def is_available() -> bool:
    """LM Studio 서버 연결 확인."""
    try:
        resp = requests.get(f"{LMSTUDIO_BASE_URL}/v1/models", timeout=3)
        return resp.status_code == 200
    except:
        return False
