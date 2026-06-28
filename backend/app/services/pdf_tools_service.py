"""PDF toolbox: merge, split, metadata, searchable PDF (MVP)."""

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
    import fitz

    doc = fitz.open()
    for path in file_paths:
        src = fitz.open(path)
        doc.insert_pdf(src)
        src.close()
    doc.save(output_path)
    doc.close()
    logger.info(f"Merged {len(file_paths)} PDFs -> {output_path}")
    return output_path


def split_pdf(file_path: str, output_dir: str, pages: Optional[List[int]] = None) -> List[str]:
    import fitz

    os.makedirs(output_dir, exist_ok=True)
    src = fitz.open(file_path)
    outputs: List[str] = []
    page_indices = coerce_page_list(pages) or list(range(1, src.page_count + 1))
    for page_num in page_indices:
        if page_num < 1 or page_num > src.page_count:
            continue
        out_doc = fitz.open()
        out_doc.insert_pdf(src, from_page=page_num - 1, to_page=page_num - 1)
        out_path = os.path.join(output_dir, f"page_{page_num}.pdf")
        out_doc.save(out_path)
        out_doc.close()
        outputs.append(out_path)
    src.close()
    return outputs


def read_pdf_metadata(file_path: str) -> Dict[str, Any]:
    import fitz

    doc = fitz.open(file_path)
    meta = doc.metadata or {}
    info = {
        "page_count": doc.page_count,
        "metadata": dict(meta),
    }
    doc.close()
    return info


def make_searchable_pdf(input_path: str, output_path: str, text: str = "") -> str:
    """Embed a minimal text layer (MVP placeholder for OCR spans)."""
    import fitz

    doc = fitz.open(input_path)
    if text:
        page = doc[0]
        rect = fitz.Rect(72, 72, 400, 100)
        page.insert_textbox(rect, text, fontsize=8, color=(1, 1, 1))
    doc.save(output_path)
    doc.close()
    return output_path


def fill_acroform(input_path: str, output_path: str, field_values: Dict[str, str]) -> str:
    import fitz

    doc = fitz.open(input_path)
    for page in doc:
        for widget in page.widgets() or []:
            name = widget.field_name
            if name and name in field_values:
                widget.field_value = field_values[name]
                widget.update()
    doc.save(output_path)
    doc.close()
    return output_path
