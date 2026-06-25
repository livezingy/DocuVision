"""Pro wrapper for docuvision-core digital PDF table extraction (Lite-equivalent Smart route)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pdfplumber
from loguru import logger

from docuvision_core.processing.table_processor import TableProcessor
from docuvision_core.processing.table_result_mapper import processor_results_to_tables
from docuvision_core.processing.table_stitch import stitch_tables_by_header


def extract_digital_pdf_tables(
    file_path: str,
    *,
    max_pages: int = 50,
    score_threshold: float = 0.5,
    table_areas: Optional[List[List[float]]] = None,
    table_template: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Extract tables from born-digital PDF using docuvision-core TableProcessor."""
    del table_template  # applied in orchestrator table_step after extraction
    processor_params: Dict[str, Any] = {
        "table_method": "mixed",
        "flavor": "auto",
        "score_threshold": score_threshold,
        "smart_camelot_fallback_threshold": 0.8,
    }
    if table_areas:
        processor_params["table_areas"] = table_areas

    processor = TableProcessor(processor_params)

    tables: List[Dict[str, Any]] = []
    with pdfplumber.open(file_path) as pdf:
        page_count = min(len(pdf.pages), max_pages)
        for page_num in range(1, page_count + 1):
            page = pdf.pages[page_num - 1]
            try:
                raw_list = processor.process_pdf_page(file_path, page)
            except Exception as exc:
                logger.warning(f"Core table extraction failed on page {page_num}: {exc}")
                continue
            tables.extend(processor_results_to_tables(raw_list or [], page_num))

    logger.info(f"Core digital PDF tables extracted: {len(tables)} from {file_path}")
    if not tables:
        try:
            from app.services.pymupdf_table_engine import extract_tables_pymupdf

            tables = extract_tables_pymupdf(file_path)
        except Exception as pymupdf_exc:
            logger.debug(f"PyMuPDF table fallback skipped: {pymupdf_exc}")
    if len(tables) > 1:
        tables = stitch_tables_by_header(tables)
    return tables
