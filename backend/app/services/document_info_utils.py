"""Helpers for document_info fields on Pro analyze results."""

from __future__ import annotations

import os
from typing import Any, Dict

from app.services.pdf_raster import pdf_page_count


def resolve_document_page_count(file_path: str, result: Dict[str, Any]) -> int:
    """Return total pages for UI (PDF page count preferred)."""
    ext = os.path.splitext(file_path or "")[1].lower()
    if ext == ".pdf":
        count = pdf_page_count(file_path)
        if count > 0:
            return count

    doc_info = result.get("document_info") if isinstance(result.get("document_info"), dict) else {}
    pages = doc_info.get("pages")
    if isinstance(pages, int) and pages > 0:
        return pages

    layout = result.get("layout") if isinstance(result.get("layout"), dict) else {}
    total_pages = layout.get("total_pages")
    if isinstance(total_pages, int) and total_pages > 0:
        return total_pages

    view = result.get("view") if isinstance(result.get("view"), dict) else {}
    view_pages = view.get("pages")
    if isinstance(view_pages, list) and len(view_pages) > 0:
        return len(view_pages)

    page_count = result.get("page_count")
    if isinstance(page_count, int) and page_count > 0:
        return page_count

    return 1
