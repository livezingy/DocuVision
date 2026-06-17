"""Born-digital vs scan PDF detection for Pro routing."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Tuple

import pdfplumber


class DetectedFileType(str, Enum):
    PDF_DIGITAL = "pdf_digital"
    PDF_SCAN = "pdf_scan"
    IMAGE = "image"
    UNSUPPORTED = "unsupported"


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def detect_file_type(file_path: str) -> Tuple[DetectedFileType, int]:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _detect_pdf_type(path)

    if suffix in IMAGE_EXTENSIONS:
        return DetectedFileType.IMAGE, 1

    return DetectedFileType.UNSUPPORTED, 0


def _detect_pdf_type(file_path: Path) -> Tuple[DetectedFileType, int]:
    with pdfplumber.open(str(file_path)) as pdf:
        page_count = len(pdf.pages)
        if page_count == 0:
            return DetectedFileType.UNSUPPORTED, 0

        sample_pages = pdf.pages[: min(3, page_count)]
        chars = 0
        for page in sample_pages:
            text = page.extract_text() or ""
            chars += len(text.strip())

        if chars >= 30:
            return DetectedFileType.PDF_DIGITAL, page_count
        return DetectedFileType.PDF_SCAN, page_count
