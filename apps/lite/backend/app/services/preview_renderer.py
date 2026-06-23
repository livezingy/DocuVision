"""Server-side page rasterization for Lite preview (aligned with Pro /page-image)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi import HTTPException


def resolve_page_count(file_path: Path) -> int:
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(file_path))
            try:
                return max(1, len(doc))
            finally:
                doc.close()
        except ImportError as exc:
            raise HTTPException(
                status_code=500,
                detail="PyMuPDF is required for PDF preview. Install docuvision-core[lite].",
            ) from exc
    return 1


def render_page_png(file_path: Path, page_num: int) -> bytes:
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return _render_pdf_page_png(file_path, page_num)
    if ext in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}:
        if page_num != 1:
            raise HTTPException(status_code=400, detail="Image preview supports page 1 only")
        return file_path.read_bytes()
    raise HTTPException(status_code=400, detail=f"Unsupported preview file type: {ext}")


def _render_pdf_page_png(file_path: Path, page_num: int) -> bytes:
    try:
        import fitz  # PyMuPDF
        from PIL import Image
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="PyMuPDF and Pillow are required for PDF preview.",
        ) from exc

    try:
        doc = fitz.open(str(file_path))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to open PDF: {exc}") from exc

    try:
        if page_num < 1 or page_num > len(doc):
            raise HTTPException(
                status_code=400,
                detail=f"Page number {page_num} out of range (1-{len(doc)})",
            )
        page = doc[page_num - 1]
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        if pix.alpha:
            img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples).convert("RGB")
        else:
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    finally:
        doc.close()

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
