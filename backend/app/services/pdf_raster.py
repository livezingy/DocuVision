"""PDF page rasterization helpers (Pro KIE / layout)."""

from __future__ import annotations

import logging
import os
import tempfile
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def pdf_page_count(file_path: str) -> int:
    ext = os.path.splitext(file_path or "")[1].lower()
    if ext != ".pdf":
        return 1
    try:
        import pypdfium2
    except ImportError:
        return 1
    try:
        with pypdfium2.PdfDocument(file_path) as pdf:
            return len(pdf)
    except Exception:
        logger.warning("pdf_page_count: cannot open %s", file_path)
        return 0


def rasterize_pdf_page(
    file_path: str,
    page_num: int,
    *,
    matrix_scale: float = 2.0,
) -> Tuple[str, Optional[str]]:
    """
    Rasterize one 1-based PDF page to a temp PNG.

    Returns (image_path, temp_path_to_delete). On failure returns (file_path, None).
    """
    import pypdfium2

    try:
        pdf = pypdfium2.PdfDocument(file_path)
    except Exception:
        logger.warning("rasterize_pdf_page: cannot open %s", file_path)
        return file_path, None
    try:
        # init_forms 必须在 pdf[i] 取页前调用（formenv 在取柄时绑定）；普通 PDF 无害 no-op。
        pdf.init_forms()
        if page_num < 1 or page_num > len(pdf):
            return file_path, None
        page = pdf[page_num - 1]
        # render(scale=matrix_scale) ↔ fitz Matrix(scale, scale)；to_pil() 恒为 RGB 3 通道
        img = page.render(scale=matrix_scale).to_pil()
        fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix=f"kie_pdf_p{page_num}_")
        os.close(fd)
        img.save(tmp_path, format="PNG")
        return tmp_path, tmp_path
    finally:
        pdf.close()
