"""Born-digital vs scan PDF detection for Pro routing.

Per-page judgement via :mod:`app.services.page_text_trust`. The legacy
"first 3 pages accumulate 30 chars" rule is removed — it misclassified
scanned PDFs carrying an OCR text layer as born-digital 100% of the time.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.services.page_text_trust import judge_page_trust


class DetectedFileType(str, Enum):
    PDF_DIGITAL = "pdf_digital"
    PDF_SCAN = "pdf_scan"
    IMAGE = "image"
    UNSUPPORTED = "unsupported"


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def detect_file_type_pages(file_path: str) -> Dict[str, Any]:
    """Per-page trust judgement for a PDF.

    Returns a dict with:
      * ``page_count``: number of pages
      * ``page_types``: per-page ``"digital"`` / ``"scan"``
      * ``page_verdicts``: per-page raw verdict from ``judge_page_trust``
      * ``page_confidences``: per-page confidence
      * ``born_digital``: True only when EVERY page is trusted text_layer

    Mixed PDFs are handled naturally (per-page verdicts).
    """
    path = Path(file_path)
    if path.suffix.lower() != ".pdf":
        return {
            "page_count": 0,
            "page_types": [],
            "page_verdicts": [],
            "page_confidences": [],
            "born_digital": False,
        }

    import fitz

    page_types: List[str] = []
    page_verdicts: List[str] = []
    page_confidences: List[float] = []

    try:
        with fitz.open(str(path)) as doc:
            for page in doc:
                result = judge_page_trust(page)
                page_verdicts.append(result.verdict)
                page_confidences.append(result.confidence)
                page_types.append("digital" if result.trusted else "scan")
    except Exception:
        return {
            "page_count": 0,
            "page_types": [],
            "page_verdicts": [],
            "page_confidences": [],
            "born_digital": False,
        }

    born_digital = bool(page_verdicts) and all(
        v == "text_layer" for v in page_verdicts
    )
    return {
        "page_count": len(page_verdicts),
        "page_types": page_types,
        "page_verdicts": page_verdicts,
        "page_confidences": page_confidences,
        "born_digital": born_digital,
    }


def detect_file_type(file_path: str) -> Tuple[DetectedFileType, int]:
    """Document-level file type (backward-compatible signature).

    ``born_digital`` = all pages trusted text_layer; otherwise scan.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        info = detect_file_type_pages(file_path)
        page_count = info["page_count"]
        if page_count == 0:
            return DetectedFileType.UNSUPPORTED, 0
        if info["born_digital"]:
            return DetectedFileType.PDF_DIGITAL, page_count
        return DetectedFileType.PDF_SCAN, page_count

    if suffix in IMAGE_EXTENSIONS:
        return DetectedFileType.IMAGE, 1

    return DetectedFileType.UNSUPPORTED, 0
