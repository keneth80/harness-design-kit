"""LLM 없음 — 정적 분석만 동작"""
from typing import Optional
BASE_URL = ""
DEFAULT_MODEL = ""

def ask(prompt, system="", model="", **kwargs): return None
def ask_json(prompt, system="", model=""): return None
def is_available(): return False
