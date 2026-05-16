"""PDF → PNG 렌더링 테스트."""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from src.memory.pdf_render import (
    PdfRenderError,
    RenderedPage,
    page_count,
    render_pdf,
)


# 최소 유효 PDF (test_text_extractor.py와 동일)
_MIN_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 24 Tf 100 700 Td (Hello PDF) Tj ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f\x20
0000000009 00000 n\x20
0000000058 00000 n\x20
0000000109 00000 n\x20
0000000228 00000 n\x20
0000000316 00000 n\x20
trailer
<< /Size 6 /Root 1 0 R >>
startxref
389
%%EOF
"""


@pytest.fixture
def pdf_path(tmp_path) -> Path:
    p = tmp_path / "test.pdf"
    p.write_bytes(_MIN_PDF)
    return p


def _is_png(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def _is_jpeg(data: bytes) -> bool:
    return data[:3] == b"\xff\xd8\xff"


# ─── 기본 렌더링 ───────────────────────────────────
def test_render_single_page(pdf_path):
    pages = render_pdf(pdf_path)
    assert len(pages) == 1
    p = pages[0]
    assert isinstance(p, RenderedPage)
    assert p.page_number == 1
    assert _is_png(p.png_bytes)
    assert p.width > 0 and p.height > 0


def test_render_dpi_scales_size(pdf_path):
    p150 = render_pdf(pdf_path, dpi=150)[0]
    p300 = render_pdf(pdf_path, dpi=300)[0]
    assert p300.width > p150.width
    assert p300.height > p150.height


def test_page_count(pdf_path):
    assert page_count(pdf_path) == 1


# ─── 경계 ──────────────────────────────────────────
def test_render_out_of_range_returns_empty(pdf_path):
    # 1페이지짜리에서 start=5 → 빈 결과
    assert render_pdf(pdf_path, start=5) == []


def test_render_start_after_end_returns_empty(pdf_path):
    assert render_pdf(pdf_path, start=3, end=2) == []


def test_max_pages_capped(pdf_path):
    # 1페이지짜리 PDF이므로 max_pages가 커도 1개
    pages = render_pdf(pdf_path, max_pages=100)
    assert len(pages) == 1


# ─── 에러 ──────────────────────────────────────────
def test_render_nonexistent_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        render_pdf(tmp_path / "nope.pdf")


def test_render_non_pdf_extension_raises(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("hello")
    with pytest.raises(PdfRenderError):
        render_pdf(p)


def test_render_invalid_pdf_raises(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"not a pdf")
    with pytest.raises(PdfRenderError):
        render_pdf(p)


def test_page_count_invalid_returns_zero(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"not a pdf")
    assert page_count(p) == 0
