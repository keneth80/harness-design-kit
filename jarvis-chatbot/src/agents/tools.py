"""공용 도구. 현재는 stub (향후 web_search, file_read 등을 추가)."""
from __future__ import annotations

from typing import Any


def noop() -> dict[str, Any]:
    return {"ok": True}
