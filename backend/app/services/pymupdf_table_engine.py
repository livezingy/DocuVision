"""PyMuPDF find_tables fallback engine for Pro digital PDFs."""

from __future__ import annotations

from typing import Any, Dict, List

from loguru import logger


def extract_tables_pymupdf(file_path: str, max_pages: int = 50) -> List[Dict[str, Any]]:
    import fitz

    tables: List[Dict[str, Any]] = []
    doc = fitz.open(file_path)
    page_count = min(doc.page_count, max_pages)
    for page_num in range(page_count):
        page = doc[page_num]
        try:
            finder = page.find_tables()
            found = finder.tables if finder else []
        except Exception as exc:
            logger.debug(f"PyMuPDF find_tables unavailable on page {page_num + 1}: {exc}")
            continue
        for idx, table in enumerate(found):
            try:
                df = table.to_pandas()
                data = [df.columns.tolist()] + df.values.tolist()
            except Exception:
                data = table.extract()
            tables.append(
                {
                    "page": page_num + 1,
                    "data": data,
                    "score": 0.7,
                    "source": "pymupdf_find_tables",
                    "engine_used": "pymupdf",
                }
            )
    doc.close()
    return tables
