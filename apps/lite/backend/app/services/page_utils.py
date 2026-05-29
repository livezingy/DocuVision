"""Page selection and rasterization helpers for Lite pipelines."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None  # type: ignore


def parse_pages_spec(pages_spec: Optional[str], page_count: int) -> List[int]:
    """Return 1-based page numbers from a pages spec string."""
    if not pages_spec or pages_spec.strip().lower() == "all":
        return list(range(1, page_count + 1))
    selected: List[int] = []
    for part in pages_spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            selected.extend(range(start, end + 1))
        else:
            selected.append(int(part))
    return sorted({p for p in selected if 1 <= p <= page_count})


def is_pdf(path: Path) -> bool:
    if path.suffix.lower() == ".pdf":
        return True
    if not path.is_file():
        return False
    with path.open("rb") as handle:
        return handle.read(4) == b"%PDF"


def rasterize_pdf_pages(
    pdf_path: Path,
    *,
    page_numbers: Optional[List[int]] = None,
    max_pages: int = 10,
    dpi: int = 200,
) -> List[Tuple[int, Image.Image]]:
    """Rasterize selected PDF pages to PIL images."""
    if fitz is None:
        raise RuntimeError("PyMuPDF is required for scanned PDF processing. Install: pip install PyMuPDF")

    images: List[Tuple[int, Image.Image]] = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    with fitz.open(pdf_path) as doc:
        total = len(doc)
        if page_numbers is None:
            page_numbers = list(range(1, min(total, max_pages) + 1))
        else:
            page_numbers = page_numbers[:max_pages]

        for page_num in page_numbers:
            if page_num < 1 or page_num > total:
                continue
            page = doc[page_num - 1]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            mode = "RGB" if pix.n < 4 else "RGBA"
            image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
            if mode == "RGBA":
                image = image.convert("RGB")
            images.append((page_num, image))
    return images


def load_raster_pages(
    file_path: Path,
    *,
    page_count: int,
    pages_spec: Optional[str] = None,
    max_pages: int = 10,
) -> List[Tuple[int, Image.Image]]:
    """Load one image file or rasterize PDF pages for OCR / Transformer pipelines."""
    if is_pdf(file_path):
        capped_count = min(page_count, max_pages)
        page_numbers = parse_pages_spec(pages_spec, capped_count)
        return rasterize_pdf_pages(file_path, page_numbers=page_numbers, max_pages=max_pages)
    return [(1, Image.open(file_path).convert("RGB"))]
