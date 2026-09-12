"""Selective cell backfill (E2 / v1.8 §4).

Four-layer funnel:
  1. page gatekeeper (``page_text_trust.judge_page_trust``)
  2. candidate cell selection (regex: numbers / codes / dates / symbols)
  3. geometric alignment (derived cell bbox -> text layer words)
  4. content acceptance (normalized character comparison)

Backfill is enhancement, never replacement: any doubt keeps the vision result.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from docuvision_core.utils.pdf_text_utils import normalize_for_compare

from app.services.page_text_trust import judge_page_trust

# Pinned symbol set (v1.8 §4.1 / B2) — matches scripts/trial/symbol_benchmark.py:33.
SYMBOL_CHARS = ["✓", "⊗", "●", "○"]

_NUMBER_RE = re.compile(r"^[+\-]?[¥$€£]?\s?\d[\d,.\s]*%?$")
_DATE_RE = re.compile(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}")
_CODE_RE = re.compile(r"^[A-Za-z0-9\s\-/._]+$")

# provenance values (v1.8 §4.4; text_mismatch added in v1.8.1 §6)
PROVENANCE_VISION = "vision"
PROVENANCE_TEXT_CONFIRMED = "text_confirmed"
PROVENANCE_TEXT_BACKFILLED = "text_backfilled"
PROVENANCE_TEXT_MISMATCH = "text_mismatch"


def is_candidate_cell(text: str) -> bool:
    """Layer 2: decide if a cell text is a backfill candidate.

    Hits: numbers/amounts (with thousand separators), codes (order/IBAN/
    contract), dates, and the pinned symbol set. Long prose cells are skipped.
    """
    if not text:
        return False
    t = text.strip()
    if not t or len(t) > 40:
        return False
    if any(sym in t for sym in SYMBOL_CHARS):
        return True
    if _NUMBER_RE.match(t):
        return True
    if _DATE_RE.search(t):
        return True
    if _CODE_RE.match(t) and any(ch.isdigit() for ch in t):
        return True
    return False


def derive_cell_bbox(
    table_bbox: Dict[str, Any],
    n_rows: int,
    n_cols: int,
    row: int,
    col: int,
) -> Optional[Tuple[float, float, float, float]]:
    """Derive a cell bbox in PDF pt space from the raster-space table bbox.

    Rasterization uses ``fitz.Matrix(2, 2)``, so PDF pt = raster px / 2.
    Cells are assumed uniform (R3 fallback: SLANeXt HTML has no per-cell bbox).
    Returns None when the grid is degenerate.
    """
    if n_rows <= 0 or n_cols <= 0:
        return None
    x = float(table_bbox.get("x", 0.0)) / 2.0
    y = float(table_bbox.get("y", 0.0)) / 2.0
    w = float(table_bbox.get("width", 0.0)) / 2.0
    h = float(table_bbox.get("height", 0.0)) / 2.0
    if w <= 0 or h <= 0:
        return None
    col_w = w / n_cols
    row_h = h / n_rows
    return (
        x + col * col_w,
        y + row * row_h,
        x + (col + 1) * col_w,
        y + (row + 1) * row_h,
    )


def _extract_cell_text_layer(
    page_words: List[Any],
    bbox: Tuple[float, float, float, float],
) -> Tuple[Optional[List[Any]], Optional[set]]:
    """Collect words whose center falls inside the cell bbox.

    Returns ``(words, line_numbers)``. If any matched word's bbox crosses the
    cell boundary, return ``(None, None)`` to signal an ambiguous alignment.
    """
    in_cell: List[Any] = []
    lines: set = set()
    for w in page_words:
        if not isinstance(w, (list, tuple)) or len(w) < 5:
            continue
        x0, y0, x1, y1 = float(w[0]), float(w[1]), float(w[2]), float(w[3])
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        if not (bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3]):
            continue
        # crossing check: the whole word bbox must lie within the cell bbox
        if not (x0 >= bbox[0] and x1 <= bbox[2] and y0 >= bbox[1] and y1 <= bbox[3]):
            return None, None
        in_cell.append(w)
        if len(w) > 6:
            lines.add(w[6])
    return in_cell, lines


def backfill_table_cells(
    table: Dict[str, Any],
    page_words: List[Any],
    *,
    trusted: bool = True,
    debug_records: Optional[List[Dict[str, Any]]] = None,
    mismatch_records: Optional[List[Dict[str, Any]]] = None,
    table_id: Optional[str] = None,
    table_index: Optional[int] = None,
    page_num: Optional[int] = None,
) -> Dict[str, int]:
    """Run the funnel over one table's cells, mutating the table in place.

    Adds two parallel grids aligned with ``table["data"]``:
      * ``cell_provenance``  — per-cell "vision" | "text_confirmed" |
        "text_backfilled" | "text_mismatch" (v1.8.1: funnel④ failures are
        labeled instead of staying "vision", so review lists can be built)
      * ``cell_ocr_text``    — original OCR text (only for backfilled cells)

    When ``debug_records`` is provided, each candidate cell's alignment
    evidence is appended for human review (``debug/backfill_alignment.json``).

    When ``mismatch_records`` is provided, each mismatch appends
    ``{page, table_index, row, col, ocr_text, text_layer_text}`` (the cell
    value is never replaced — ``text_layer_text`` is "" when no single text
    layer line could be aligned).

    Returns per-table counts (candidates/confirmed/backfilled/mismatch).
    """
    stats = {"candidates": 0, "confirmed": 0, "backfilled": 0, "mismatch": 0}
    data = table.get("data")
    if not isinstance(data, list) or not data:
        return stats
    n_rows = len(data)
    n_cols = max((len(r) for r in data if isinstance(r, list)), default=0)
    if n_cols <= 0:
        return stats
    table_bbox = table.get("bbox") or {}

    cell_provenance: List[List[str]] = []
    cell_ocr_text: List[List[Optional[str]]] = []

    for i, row in enumerate(data):
        if not isinstance(row, list):
            row = [str(row)]
            data[i] = row
        prov_row: List[str] = []
        ocr_row: List[Optional[str]] = []
        for j, cell_text in enumerate(row):
            prov_row.append(PROVENANCE_VISION)
            ocr_row.append(None)

            if not trusted:
                continue
            if not cell_text or not str(cell_text).strip():
                continue
            if not is_candidate_cell(str(cell_text)):
                continue

            stats["candidates"] += 1
            cell_text = str(cell_text)
            provenance = PROVENANCE_VISION
            text_layer_text = ""

            bbox = derive_cell_bbox(table_bbox, n_rows, n_cols, i, j)
            if bbox is None:
                stats["mismatch"] += 1
                provenance = PROVENANCE_TEXT_MISMATCH
            else:
                in_cell, lines = _extract_cell_text_layer(page_words, bbox)
                if in_cell is None:
                    # crossing word -> alignment failure
                    stats["mismatch"] += 1
                    provenance = PROVENANCE_TEXT_MISMATCH
                elif len(lines or []) != 1:
                    # a single grid cell should map to a single text layer line
                    stats["mismatch"] += 1
                    provenance = PROVENANCE_TEXT_MISMATCH
                else:
                    text_layer_text = " ".join(str(w[4]) for w in in_cell).strip()
                    vis_norm = normalize_for_compare(cell_text)
                    tl_norm = normalize_for_compare(text_layer_text)

                    if not tl_norm:
                        # text layer empty -> keep OCR (possibly a truly empty cell)
                        stats["mismatch"] += 1
                        provenance = PROVENANCE_TEXT_MISMATCH
                    elif vis_norm == tl_norm:
                        # consistent -> no replacement, mark confirmed
                        provenance = PROVENANCE_TEXT_CONFIRMED
                        prov_row[j] = PROVENANCE_TEXT_CONFIRMED
                        stats["confirmed"] += 1
                    else:
                        # numeric/symbol divergence -> text layer wins
                        provenance = PROVENANCE_TEXT_BACKFILLED
                        prov_row[j] = PROVENANCE_TEXT_BACKFILLED
                        ocr_row[j] = cell_text
                        row[j] = text_layer_text
                        stats["backfilled"] += 1

            if provenance == PROVENANCE_TEXT_MISMATCH:
                prov_row[j] = PROVENANCE_TEXT_MISMATCH
                if mismatch_records is not None:
                    mismatch_records.append(
                        {
                            "page": page_num,
                            "table_index": table_index,
                            "row": i,
                            "col": j,
                            "ocr_text": cell_text,
                            "text_layer_text": text_layer_text,
                        }
                    )

            if debug_records is not None:
                debug_records.append(
                    {
                        "page": page_num,
                        "table_id": table_id,
                        "row": i,
                        "col": j,
                        "bbox": [round(v, 2) for v in bbox] if bbox is not None else None,
                        "visual": cell_text,
                        "text_layer": text_layer_text,
                        "provenance": provenance,
                    }
                )

        cell_provenance.append(prov_row)
        cell_ocr_text.append(ocr_row)

    table["cell_provenance"] = cell_provenance
    table["cell_ocr_text"] = cell_ocr_text
    return stats


def backfill_tables(
    tables: List[Dict[str, Any]],
    file_path: str,
    *,
    enabled: bool = True,
    debug_dir: Optional[str] = None,
    angle_deg: float = 0.0,
    use_doc_unwarping: bool = False,
) -> Dict[str, Any]:
    """Backfill a document's tables in place; return the quality summary dict.

    Runs the page gatekeeper per table-bearing page, then the per-cell funnel
    on trusted pages. ``enabled=False`` short-circuits with a zero summary.

    v1.8.1 gate (§6/D10): table bboxes stay in preprocessed raster space
    (layout_service never inverse-rotates them), so when the document was
    deskewed (``angle_deg != 0``) or unwarping ran, aligning them with the
    original PDF's text layer would fabricate mismatches. Such pages are
    skipped and counted in ``pages_skipped_preprocessed``.

    When ``debug_dir`` is provided, per-candidate alignment evidence is
    written to ``debug_dir/backfill_alignment.json`` (R1 mitigation).

    The summary carries ``mismatch_details`` (capped at 50 entries of
    ``{page, table_index, row, col, ocr_text, text_layer_text}``) plus
    ``mismatch_details_truncated`` when the cap overflowed.
    """
    summary: Dict[str, Any] = {
        "enabled": bool(enabled),
        "pages_judged": 0,
        "pages_text_layer_trusted": 0,
        "pages_skipped_preprocessed": 0,
        "cells_candidates": 0,
        "cells_confirmed": 0,
        "cells_backfilled": 0,
        "cells_mismatch": 0,
        "backfill_rate": 0.0,
        "mismatch_rate": 0.0,
        "mismatch_details": [],
        "mismatch_details_truncated": 0,
        "page_verdicts": [],
    }
    if not enabled or not tables:
        return summary

    import fitz

    try:
        doc = fitz.open(file_path)
    except Exception:
        return summary

    debug_records: Optional[List[Dict[str, Any]]] = [] if debug_dir else None
    mismatch_records: List[Dict[str, Any]] = []

    try:
        tables_by_page: Dict[int, List[Tuple[int, Dict[str, Any]]]] = {}
        for t_idx, t in enumerate(tables):
            if not isinstance(t, dict):
                continue
            p = int(t.get("page", 1) or 1)
            tables_by_page.setdefault(p, []).append((t_idx, t))

        for page_num in sorted(tables_by_page):
            if page_num < 1 or page_num > len(doc):
                continue
            if use_doc_unwarping or angle_deg != 0.0:
                # v1.8.1 §6/D10: bboxes are in preprocessed raster space while
                # the PDF text layer is in original page space — never align.
                summary["pages_skipped_preprocessed"] += 1
                continue
            page = doc[page_num - 1]
            trust = judge_page_trust(page)
            summary["pages_judged"] += 1
            summary["page_verdicts"].append(trust.verdict)
            if not trust.trusted:
                continue
            # coordinate alignment requires an unrotated page (§4.2)
            if page.rotation != 0:
                continue
            summary["pages_text_layer_trusted"] += 1
            page_words = page.get_text("words")
            for t_idx, t in tables_by_page[page_num]:
                s = backfill_table_cells(
                    t,
                    page_words,
                    trusted=True,
                    debug_records=debug_records,
                    mismatch_records=mismatch_records,
                    table_id=t.get("id"),
                    table_index=t_idx,
                    page_num=page_num,
                )
                summary["cells_candidates"] += s["candidates"]
                summary["cells_confirmed"] += s["confirmed"]
                summary["cells_backfilled"] += s["backfilled"]
                summary["cells_mismatch"] += s["mismatch"]
    finally:
        doc.close()

    cand = summary["cells_candidates"]
    if cand > 0:
        summary["backfill_rate"] = round(summary["cells_backfilled"] / cand, 3)
        summary["mismatch_rate"] = round(summary["cells_mismatch"] / cand, 3)

    if mismatch_records:
        summary["mismatch_details"] = mismatch_records[:50]
        if len(mismatch_records) > 50:
            summary["mismatch_details_truncated"] = len(mismatch_records) - 50

    if debug_dir and debug_records:
        _write_debug_alignment(debug_dir, debug_records)
    return summary


def _write_debug_alignment(debug_dir: str, records: List[Dict[str, Any]]) -> None:
    """Write per-candidate alignment evidence for human review (R1)."""
    import json
    import os

    try:
        os.makedirs(debug_dir, exist_ok=True)
        path = os.path.join(debug_dir, "backfill_alignment.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception:
        # debug output must never break the task
        pass
