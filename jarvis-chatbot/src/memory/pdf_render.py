"""PDF → PNG 이미지 렌더링 (pypdfium2 + Pillow).

텔레그램으로 PDF 페이지를 사진으로 미리보기 보내기 위한 모듈.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from src.core.logger import get_logger

_log = get_logger("memory.pdf_render")

DEFAULT_DPI = 150
DEFAULT_MAX_PAGES = 5
ABSOLUTE_MAX_PAGES = 20
TELEGRAM_PHOTO_LIMIT_BYTES = 10 * 1024 * 1024  # 10MB


class PdfRenderError(Exception):
    pass


@dataclass
class RenderedPage:
    page_number: int  # 1-based
    png_bytes: bytes
    width: int
    height: int


def render_pdf(
    path: Path,
    *,
    start: int = 1,
    end: int | None = None,
    dpi: int = DEFAULT_DPI,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list[RenderedPage]:
    """PDF 파일을 페이지별 PNG bytes 리스트로 반환.

    start/end는 1-based. end=None이면 끝까지.
    max_pages 초과 시 잘려서 max_pages만 렌더.
    ABSOLUTE_MAX_PAGES(20)은 강제 상한.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".pdf":
        raise PdfRenderError(f"PDF가 아닙니다: {path.suffix}")
    try:
        import pypdfium2 as pdfium
    except ImportError as e:
        raise PdfRenderError(f"pypdfium2 import 실패: {e}") from e

    try:
        pdf = pdfium.PdfDocument(str(path))
    except Exception as e:
        raise PdfRenderError(f"PDF 열기 실패: {e}") from e

    try:
        total = len(pdf)
        if total == 0:
            return []
        start = max(1, start)
        end_eff = total if end is None else min(end, total)
        if end_eff < start:
            return []
        page_count = end_eff - start + 1
        cap = min(max_pages, ABSOLUTE_MAX_PAGES)
        if page_count > cap:
            end_eff = start + cap - 1
        scale = dpi / 72.0
        out: list[RenderedPage] = []
        for i in range(start - 1, end_eff):
            page = pdf[i]
            try:
                bitmap = page.render(scale=scale)
                try:
                    pil_image = bitmap.to_pil()
                finally:
                    bitmap.close()
            finally:
                page.close()
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG", optimize=True)
            data = buf.getvalue()
            # 텔레그램 사진 10MB 상한 — 초과 시 JPEG로 재인코딩
            if len(data) > TELEGRAM_PHOTO_LIMIT_BYTES:
                buf2 = io.BytesIO()
                pil_image.convert("RGB").save(
                    buf2, format="JPEG", quality=85, optimize=True
                )
                data = buf2.getvalue()
            out.append(
                RenderedPage(
                    page_number=i + 1,
                    png_bytes=data,
                    width=pil_image.width,
                    height=pil_image.height,
                )
            )
        return out
    finally:
        try:
            pdf.close()
        except Exception:
            pass


def page_count(path: Path) -> int:
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return 0
    try:
        pdf = pdfium.PdfDocument(str(path))
        n = len(pdf)
        pdf.close()
        return n
    except Exception as e:
        _log.warning(f"page_count failed for {path.name}: {e}")
        return 0
