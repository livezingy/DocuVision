"""Cell geometry & text-layer extraction (F1 split from ``table_backfill.py`` - P-028 PR1).

Pure move, zero behavior change (D2): the pinned symbol set, the candidate
regexes, :func:`is_candidate_cell`, :func:`derive_cell_bbox`, the text-layer
collector and the bbox helpers live here; ``table_backfill.py`` imports the
five functions back (one-way, backfill -> cell_geo, no cycle) so the
``from app.services.table_backfill import ...`` test paths stay stable.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple

# Pinned symbol set (v1.8 §4.1 / B2) — matches scripts/trial/symbol_benchmark.py:33.
SYMBOL_CHARS = ["✓", "⊗", "●", "○"]

_NUMBER_RE = re.compile(r"^[+\-]?[¥$€£]?\s?\d[\d,.\s]*%?$")
_DATE_RE = re.compile(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}")
_CODE_RE = re.compile(r"^[A-Za-z0-9\s\-/._]+$")


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


def _words_union_bbox(words: List[Any]) -> List[float]:
    """Pt-space union bbox of matched text-layer words (fitz word tuples).

    The exact printed extent of the cell's characters — the drawing anchor
    for the proof pack's green/amber boxes (guaranteed by construction)."""
    return [
        round(min(float(w[0]) for w in words), 2),
        round(min(float(w[1]) for w in words), 2),
        round(max(float(w[2]) for w in words), 2),
        round(max(float(w[3]) for w in words), 2),
    ]


def _pt_rect(table: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """Table visual bbox as an unexpanded pt rect (P-002 D9; px/2, .get() tolerance)."""
    bbox = table.get("bbox") or {}
    x = float(bbox.get("x", 0.0)) / 2.0
    y = float(bbox.get("y", 0.0)) / 2.0
    w = float(bbox.get("width", 0.0)) / 2.0
    h = float(bbox.get("height", 0.0)) / 2.0
    return (x, y, x + w, y + h)
