"""Convert docuvision_core extraction results to LiteResult tables."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from docuvision_core.utils.pdf_text_utils import sanitize_pdf_text


def _clean_cell(value: Any) -> str:
    return sanitize_pdf_text(value)


def _dataframe_to_rows(table_obj: Any) -> Tuple[List[str], List[List[str]]]:
    df = getattr(table_obj, "df", None)
    if df is None:
        return [], []
    headers = [_clean_cell(c) for c in df.columns.tolist()]
    rows = [[_clean_cell(c) for c in row] for row in df.fillna("").astype(str).values.tolist()]
    return headers, rows


def _bbox_to_list(bbox: Any) -> List[float]:
    if not bbox:
        return []
    if isinstance(bbox, (list, tuple)):
        return [float(v) for v in bbox]
    return []


def raw_results_to_lite_tables(
    raw_results: List[Dict[str, Any]],
    page: int,
    start_index: int = 0,
) -> List[Dict[str, Any]]:
    tables: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_results):
        table_obj = item.get("table")
        headers, rows = _dataframe_to_rows(table_obj)
        if not rows and table_obj is not None and hasattr(table_obj, "extract"):
            try:
                extracted = table_obj.extract() or []
                rows = [[_clean_cell(c) for c in row] for row in extracted]
            except Exception:
                rows = []

        lite_table = {
            "table_id": f"t{start_index + idx}_p{page}",
            "page": page,
            "index_on_page": idx,
            "bbox": _bbox_to_list(item.get("bbox")),
            "row_count": len(rows),
            "col_count": len(rows[0]) if rows else 0,
            "score": float(item.get("score", 0.0) or 0.0),
            "source": str(item.get("source", "")),
            "headers": headers,
            "rows": rows,
            "details": {
                "domain": str(item.get("domain", "unknown")),
                "empty_cells": 0,
                "merged_cells_detected": False,
            },
        }
        tables.append(lite_table)
    return tables
