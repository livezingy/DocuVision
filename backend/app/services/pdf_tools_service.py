"""PDF toolbox: merge, split, metadata, AcroForm fill (MVP).

Migrated from PyMuPDF (fitz) to pypdf 3.17.4 (P-046 package A).
Function signatures and return contracts are unchanged; metadata key
names differ vs. fitz (registered as an acceptable deviation: the
router passes the dict through verbatim).
"""

from __future__ import annotations

import io
import os
from typing import Any, Dict, List, Optional, Union

from loguru import logger


def coerce_page_list(pages: Union[None, int, List[Any]]) -> Optional[List[int]]:
    """Normalize page selectors to a 1-based page index list."""
    if pages is None:
        return None
    if isinstance(pages, int):
        return [pages]
    if isinstance(pages, list):
        out: List[int] = []
        for page in pages:
            try:
                out.append(int(page))
            except (TypeError, ValueError):
                continue
        return out or None
    return None


def merge_pdfs(file_paths: List[str], output_path: str) -> str:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for path in file_paths:
        writer.append(path)
    writer.write(output_path)
    logger.info(f"Merged {len(file_paths)} PDFs -> {output_path}")
    return output_path


def split_pdf(file_path: str, output_dir: str, pages: Optional[List[int]] = None) -> List[str]:
    from pypdf import PdfReader, PdfWriter

    os.makedirs(output_dir, exist_ok=True)
    reader = PdfReader(file_path)
    page_count = len(reader.pages)
    outputs: List[str] = []
    page_indices = coerce_page_list(pages) or list(range(1, page_count + 1))
    for page_num in page_indices:
        if page_num < 1 or page_num > page_count:
            continue
        writer = PdfWriter()
        writer.add_page(reader.pages[page_num - 1])
        out_path = os.path.join(output_dir, f"page_{page_num}.pdf")
        writer.write(out_path)
        outputs.append(out_path)
    return outputs


def read_pdf_metadata(file_path: str) -> Dict[str, Any]:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    info = reader.metadata
    meta: Dict[str, Any] = {}
    if info is not None:
        # pypdf property names (fitz used title/author/subject/creator/
        # producer/creationDate/modDate; pypdf uses creation_date and
        # modification_date). Values are stringified so the dict stays
        # JSON-serializable (pypdf parses dates into datetime objects).
        for key in (
            "title",
            "author",
            "subject",
            "creator",
            "producer",
            "creation_date",
            "modification_date",
        ):
            value = getattr(info, key, None)
            if value is not None:
                meta[key] = str(value)
    return {
        "page_count": len(reader.pages),
        "metadata": meta,
    }


def fill_acroform(input_path: str, output_path: str, field_values: Dict[str, str]) -> str:
    from pypdf import PdfWriter

    writer = PdfWriter(clone_from=input_path)
    for page in writer.pages:
        try:
            # auto_regenerate=True sets /NeedAppearances=True in the
            # AcroForm dict (pypdf _writer.py set_need_appearances_writer),
            # the equivalent of fitz's widget.update() appearance refresh.
            writer.update_page_form_field_values(page, field_values, auto_regenerate=True)
        except Exception:
            # Per-page tolerance: pages without annots / AcroForm-less
            # documents (pypdf raises PyPdfError) are skipped, matching
            # the previous fitz no-widget no-op behavior.
            continue
    writer.write(output_path)
    return output_path
