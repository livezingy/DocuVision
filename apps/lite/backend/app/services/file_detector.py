"""File type detection for Lite auto-routing."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Tuple

import pdfplumber

from app.schemas.lite_result import DetectedFileType

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def detect_file_type(file_path: Path, mime_type: str | None = None) -> Tuple[DetectedFileType, int]:
    """Return detected type and page count (PDF) or 1 for images."""
    suffix = file_path.suffix.lower()
    mime = mime_type or mimetypes.guess_type(str(file_path))[0] or ""

    if suffix == ".pdf" or mime == "application/pdf":
        return _detect_pdf_type(file_path)

    if suffix in IMAGE_EXTENSIONS or mime.startswith("image/"):
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
