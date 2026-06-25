"""Convert TableProcessor raw results to API-facing table dicts."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

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


def _rows_to_data_grid(headers: List[str], rows: List[List[str]]) -> List[List[str]]:
    if headers:
        return [headers] + rows
    return list(rows)


def processor_results_to_tables(
    raw_results: List[Dict[str, Any]],
    page: int,
    *,
    start_index: int = 0,
) -> List[Dict[str, Any]]:
    """Map TableProcessor page results to tables with headers, rows, and data grid."""
    tables: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_results or []):
        if not isinstance(item, dict):
            continue
        table_obj = item.get("table")
        headers, rows = _dataframe_to_rows(table_obj)
        if not rows and table_obj is not None and hasattr(table_obj, "extract"):
            try:
                extracted = table_obj.extract() or []
                rows = [[_clean_cell(c) for c in row] for row in extracted]
            except Exception:
                rows = []

        data = item.get("data")
        if not data:
            data = _rows_to_data_grid(headers, rows)

        bbox = item.get("bbox")
        bbox_list: List[float] = []
        if isinstance(bbox, (list, tuple)):
            bbox_list = [float(v) for v in bbox]

        tables.append(
            {
                "table_id": f"t{start_index + idx}_p{page}",
                "page": page,
                "index_on_page": idx,
                "bbox": bbox_list,
                "row_count": len(rows),
                "col_count": len(rows[0]) if rows else (len(headers) if headers else 0),
                "score": float(item.get("score", 0.0) or 0.0),
                "source": str(item.get("source", "docuvision_core")),
                "engine_used": "docuvision_core",
                "headers": headers,
                "rows": rows,
                "data": data,
            }
        )
    return tables
