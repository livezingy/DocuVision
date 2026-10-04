"""Selective cell backfill (E2 / v1.8 §4).

Four-layer funnel: page gatekeeper -> candidate selection -> geometric
alignment -> content acceptance. P-002 adds the T1 value-match layer and the
amber sanity gate (see ``table_alignment``). Enhancement, never replacement:
any doubt keeps the vision result.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from docuvision_core.utils.pdf_text_utils import normalize_for_compare

from app.services.page_text_trust import judge_page_trust
from app.services.table_alignment import (
    REASON_CROSSING, REASON_GEO, REASON_KEYS, REASON_MULTI, REASON_NO_LINE,
    REASON_SANITY, REASON_SHAPE, REASON_VALUE_MATCH, LayoutModel, T1Status,
    build_layout_model, is_ocr_confusion, resolve_t1_collision, solve_t1,
    solve_t3,
)

from app.services.table_cell_geo import (
    _extract_cell_text_layer,
    _pt_rect,
    _words_union_bbox,
    derive_cell_bbox,
    is_candidate_cell,
)

# provenance values (v1.8 §4.4; text_mismatch added in v1.8.1 §6)
PROVENANCE_VISION = "vision"
PROVENANCE_TEXT_CONFIRMED = "text_confirmed"
PROVENANCE_TEXT_BACKFILLED = "text_backfilled"
PROVENANCE_TEXT_MISMATCH = "text_mismatch"


def _solve_candidate(
    model: LayoutModel,
    table_bbox: Dict[str, Any],
    page_words: List[Any],
    n_rows: int,
    n_cols: int,
    i: int,
    j: int,
    cell_text: str,
) -> Tuple[str, str, Optional[List[Any]], str, Optional[Tuple[float, float, float, float]]]:
    """Resolve one candidate cell through the layer pipeline (P-002 §3.6).

    T1 anchored value match first; on failure the unchanged T2 geometric
    gates decide, and T3 (text-cluster mapping) rescues those gate failures
    or keeps the honest red. Returns ``(provenance, reason, words,
    text_layer_text, derived bbox)``; bbox is None when T1 solved or the grid
    was degenerate.
    """
    t1_status, t1_words = solve_t1(model, cell_text, i, j)
    if t1_status == T1Status.UNIQUE:
        return (
            PROVENANCE_TEXT_CONFIRMED, REASON_VALUE_MATCH, t1_words,
            " ".join(str(w[4]) for w in t1_words), None,
        )
    if t1_status == T1Status.COLLISION:
        ok, t1_words = resolve_t1_collision(model, cell_text, i, j)
        if ok:
            return (
                PROVENANCE_TEXT_CONFIRMED, REASON_VALUE_MATCH, t1_words,
                " ".join(str(w[4]) for w in t1_words), None,
            )
        # unresolved same-row collision -> fall through to T2 (§3.3 step 5)

    # T2: geometric inclusion (existing three gates, logic unchanged)
    bbox = derive_cell_bbox(table_bbox, n_rows, n_cols, i, j)
    if bbox is None:
        return (PROVENANCE_TEXT_MISMATCH, REASON_SHAPE, None, "", None)  # terminal
    in_cell, lines = _extract_cell_text_layer(page_words, bbox)
    t2_fail_reason = None
    if in_cell is None:
        t2_fail_reason = REASON_CROSSING  # crossing word
    elif not in_cell:
        t2_fail_reason = REASON_NO_LINE
    elif len(lines or []) != 1:
        # a single grid cell should map to a single text layer line
        t2_fail_reason = REASON_MULTI
    if t2_fail_reason is not None:
        # T3 rescues the T2 gate failure or keeps the honest red
        prov, reason, words = solve_t3(model, cell_text, i, j, t2_fail_reason)
        tl = " ".join(str(w[4]) for w in words) if words else ""
        return (prov, reason, words, tl, bbox)
    text_layer_text = " ".join(str(w[4]) for w in in_cell).strip()
    vis_norm = normalize_for_compare(cell_text)
    tl_norm = normalize_for_compare(text_layer_text)
    if not tl_norm:
        # text layer empty -> keep OCR (possibly a truly empty cell)
        return (PROVENANCE_TEXT_MISMATCH, REASON_NO_LINE, None, text_layer_text, bbox)
    if vis_norm == tl_norm:
        return (PROVENANCE_TEXT_CONFIRMED, REASON_GEO, in_cell, text_layer_text, bbox)
    if is_ocr_confusion(vis_norm, tl_norm):
        # numeric/symbol divergence in a confusion shape -> text layer wins
        return (PROVENANCE_TEXT_BACKFILLED, REASON_GEO, in_cell, text_layer_text, bbox)
    # not a confusion shape: data stays untouched (sanity gate, spec §4.2)
    return (PROVENANCE_TEXT_MISMATCH, REASON_SANITY, in_cell, text_layer_text, bbox)


def _finalize(
    *,
    provenance: str, reason: str, words: Optional[List[Any]],
    text_layer_text: str, cell_text: str, i: int, j: int, row: List[Any],
    prov_row: List[str], ocr_row: List[Optional[str]],
    wb_row: List[Optional[List[float]]], reason_row: List[Optional[str]],
    stats: Dict[str, Any], reason_counts: Dict[str, int],
) -> None:
    """Single write point for one candidate cell's outcome (P-002 §3.3.1-e)."""
    prov_row[j] = provenance
    reason_row[j] = reason
    if provenance == PROVENANCE_TEXT_BACKFILLED:
        ocr_row[j] = cell_text  # keep the OCR original
        row[j] = text_layer_text  # text layer wins
    if provenance in (PROVENANCE_TEXT_CONFIRMED, PROVENANCE_TEXT_BACKFILLED) and words:
        wb_row[j] = _words_union_bbox(words)  # mismatch cells get no anchor
    if provenance == PROVENANCE_TEXT_CONFIRMED:
        stats["confirmed"] += 1
    elif provenance == PROVENANCE_TEXT_BACKFILLED:
        stats["backfilled"] += 1
    else:
        stats["mismatch"] += 1
    reason_counts[reason] = reason_counts.get(reason, 0) + 1


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
    sibling_bboxes: Optional[List[Tuple[float, float, float, float]]] = None,
) -> Dict[str, Any]:
    """Run the funnel over one table's cells, mutating the table in place.

    Three-layer alignment (P-002 §3.6): T1 anchored value match first, then
    the unchanged T2 geometric gates; the amber branch (data replacement) is
    guarded by the ``is_ocr_confusion`` sanity gate.

    Adds four grids aligned with ``table["data"]``:
      * ``cell_provenance`` — "vision" | "text_confirmed" | "text_backfilled"
        | "text_mismatch" (v1.8.1: failures are labeled, not left "vision")
      * ``cell_ocr_text`` — original OCR text (only for backfilled cells)
      * ``cell_word_bbox`` — pt-space union bbox of the matched text-layer
        words (confirmed/backfilled only; the proof pack's green/amber
        anchor, accurate by construction)
      * ``cell_align_reason`` — P-002 8-value reason for candidate cells,
        None for non-candidates (vision / empty / not a candidate)

    ``debug_records`` appends per-candidate evidence
    (``debug/backfill_alignment.json``); ``mismatch_records`` appends
    ``{page, table_index, row, col, ocr_text, text_layer_text, reason}`` (the
    cell value is never replaced on mismatch). ``sibling_bboxes`` are the
    other same-page tables' pt rects (D9); words centered inside a sibling
    never enter the T1 neighborhood. Returns the per-table counts plus
    ``align_reason_counts`` (8 keys, always present, sum == candidates).
    """
    stats: Dict[str, Any] = {"candidates": 0, "confirmed": 0, "backfilled": 0, "mismatch": 0}
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
    cell_word_bbox: List[List[Optional[List[float]]]] = []
    cell_align_reason: List[List[Optional[str]]] = []

    # P-002: layout model built once per table (T1 and T3 share it)
    model = (
        build_layout_model(table_bbox, page_words, n_rows, n_cols, sibling_bboxes)
        if trusted
        else None
    )
    reason_counts: Dict[str, int] = {key: 0 for key in REASON_KEYS}

    for i, row in enumerate(data):
        if not isinstance(row, list):
            row = [str(row)]
            data[i] = row
        prov_row: List[str] = []
        ocr_row: List[Optional[str]] = []
        wb_row: List[Optional[List[float]]] = []
        reason_row: List[Optional[str]] = []
        for j, cell_text in enumerate(row):
            prov_row.append(PROVENANCE_VISION)
            ocr_row.append(None)
            wb_row.append(None)
            reason_row.append(None)

            if not trusted:
                continue
            if not cell_text or not str(cell_text).strip():
                continue
            if not is_candidate_cell(str(cell_text)):
                continue

            stats["candidates"] += 1
            cell_text = str(cell_text)
            provenance, reason, words, text_layer_text, bbox = _solve_candidate(
                model, table_bbox, page_words, n_rows, n_cols, i, j, cell_text
            )
            _finalize(
                provenance=provenance, reason=reason, words=words,
                text_layer_text=text_layer_text, cell_text=cell_text,
                i=i, j=j, row=row, prov_row=prov_row, ocr_row=ocr_row,
                wb_row=wb_row, reason_row=reason_row, stats=stats,
                reason_counts=reason_counts,
            )

            if provenance == PROVENANCE_TEXT_MISMATCH and mismatch_records is not None:
                mismatch_records.append({
                    "page": page_num,
                    "table_index": table_index,
                    "row": i,
                    "col": j,
                    "ocr_text": cell_text,
                    "text_layer_text": text_layer_text,
                    "reason": reason,
                })

            if debug_records is not None:
                debug_records.append({
                    "page": page_num,
                    "table_id": table_id,
                    "row": i,
                    "col": j,
                    "bbox": [round(v, 2) for v in bbox] if bbox is not None else None,
                    "visual": cell_text,
                    "text_layer": text_layer_text,
                    "provenance": provenance,
                    "reason": reason,
                })

        cell_provenance.append(prov_row)
        cell_ocr_text.append(ocr_row)
        cell_word_bbox.append(wb_row)
        cell_align_reason.append(reason_row)

    table["cell_provenance"] = cell_provenance
    table["cell_ocr_text"] = cell_ocr_text
    table["cell_word_bbox"] = cell_word_bbox
    table["cell_align_reason"] = cell_align_reason
    stats["align_reason_counts"] = reason_counts
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

    The summary carries ``mismatch_details`` (capped at 50 entries of
    ``{page, table_index, row, col, ocr_text, text_layer_text, reason}``) plus
    ``mismatch_details_truncated`` when the cap overflowed; with ``debug_dir``
    set, per-candidate evidence lands in ``backfill_alignment.json`` (R1).
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
    summary["align_reason_counts"] = {key: 0 for key in REASON_KEYS}
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
            page_tables = tables_by_page[page_num]
            for t_idx, t in page_tables:
                # P-002 D9: sibling pt rects — words centered inside a sibling
                # never enter this table's T1 neighborhood
                siblings = [
                    _pt_rect(other) for _, other in page_tables if other is not t
                ]
                s = backfill_table_cells(
                    t,
                    page_words,
                    trusted=True,
                    debug_records=debug_records,
                    mismatch_records=mismatch_records,
                    table_id=t.get("id"),
                    table_index=t_idx,
                    page_num=page_num,
                    sibling_bboxes=siblings,
                )
                summary["cells_candidates"] += s["candidates"]
                summary["cells_confirmed"] += s["confirmed"]
                summary["cells_backfilled"] += s["backfilled"]
                summary["cells_mismatch"] += s["mismatch"]
                for key, val in s["align_reason_counts"].items():
                    summary["align_reason_counts"][key] += val
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
        _write_debug_json(debug_dir, "backfill_alignment.json", debug_records)
    return summary


def _write_debug_json(debug_dir: str, filename: str, payload: Any) -> None:
    """Write one debug artifact for human review (R1); never breaks the task."""
    import json
    import os

    try:
        os.makedirs(debug_dir, exist_ok=True)
        path = os.path.join(debug_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        # debug output must never break the task
        pass
