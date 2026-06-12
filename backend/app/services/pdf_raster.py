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
        import fitz
    except ImportError:
        return 1
    try:
        with fitz.open(file_path) as doc:
            return len(doc)
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
    import fitz
    from PIL import Image

    try:
        doc = fitz.open(file_path)
    except Exception:
        logger.warning("rasterize_pdf_page: cannot open %s", file_path)
        return file_path, None
    try:
        if page_num < 1 or page_num > len(doc):
            return file_path, None
        page = doc[page_num - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(matrix_scale, matrix_scale))
        if pix.alpha:
            img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
            img = img.convert("RGB")
        else:
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix=f"kie_pdf_p{page_num}_")
        os.close(fd)
        img.save(tmp_path, format="PNG")
        return tmp_path, tmp_path
    finally:
        doc.close()
