"""D8 (P-027 产品侧立项 D8): per-cell confidence from PP-StructureV3 table OCR scores.

Source, measured on the pinned stack (Cloud GPU box, 2026-10-09, ``63ea47e``, paddleocr
3.3.2 / paddlex 3.3.12): a single PP-StructureV3 call returns, per table,
``table_res_list[].cell_box_list`` (cell boxes as four numbers ``[x0, y0, x1, y1]``) next to
``table_ocr_pred`` = ``{rec_boxes, rec_polys, rec_scores, rec_texts}`` - the recognition
results of that table, where ``rec_scores`` are the PaddleOCR recognition scores. In every
fixture probed ``rec_boxes`` and ``rec_polys`` were byte-identical, and the ``<td>/<th>``
count of ``pred_html`` equalled ``len(cell_box_list)``.

Two measured facts shape this module.

1. **Entries are not one-per-cell.** On ``test_data/testfiles/pdf/sample_report.pdf`` a single
   cell held up to 3 entries and the entry boxes covered a median 0.24 of their cell's area
   (min 0.03) - they are text-line sized. On
   ``test_data/testfiles/invoices/multipage/invoice_multipage_3p_items.pdf`` the entry boxes
   matched the cells (median 0.67) and 26 entries covered 26 of 32 cells, the remaining 6
   being empty ``<td>``s (``len(cell_box_list)=32``, 26 entries). Aggregation therefore
   **groups by containing cell** and keeps the **min** score.

2. **The frame cannot be assumed.** On ``test_data/testfiles/GeneralFiles/bank_statement_sample.pdf``
   all 19 entry boxes fell outside all 20 cell boxes, while ``page_height - y`` put all 19
   inside (that page has rotation 0 and a standard MediaBox, so it is not a page-attribute
   effect, and ``rec_polys`` was identical to ``rec_boxes``). Flipping the y axis broke the
   other two fixtures, so no single frame rule works: the frame is chosen **per table** by
   containment, guarded by a hit-rate threshold. Below the threshold the whole table is
   reported **unmeasured** (``measured=False``, every cell ``None``) plus an anomaly reason,
   never a silent all-``None``-per-cell or all-1.0 table.

Cells with no entry are ``None`` - "unmeasured != 0", the same semantics the external harness
uses for its gate 3 (PENDING P-027 R3/R4). This module is pure: no Paddle, no I/O, no
``self`` state, so the aggregation rules are unit-testable on the local box.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

Box = Tuple[float, float, float, float]

#: Minimum share of entries that must land inside a cell for a table to be considered
#: measured. Calibrated on the three Cloud readings above (1.00 / 0.92 / 1.00 for the chosen
#: frame, and 0.00 for the rejected one), so the margin is wide; kept as a named constant so
#: the adjudication is visible.
DEFAULT_FRAME_OK_RATIO = 0.8


def _flatten(value: Any) -> List[float]:
    """Flatten arbitrarily nested numeric sequences (a numpy row is not a list).

    Strings/bytes are refused outright: they are iterable, so recursing into them would spin.
    """
    if isinstance(value, (str, bytes)):
        return []
    out: List[float] = []
    try:
        items = list(value)
    except TypeError:
        return out
    for item in items:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            out.extend(_flatten(item))
    return out


def as_box(value: Any) -> Optional[Box]:
    """Normalise a cell/entry box to ``(x0, y0, x1, y1)``.

    Accepts the two shapes the engine emits: four numbers ``[x0, y0, x1, y1]``
    (``cell_box_list`` entries) and eight numbers / a ``(4, 2)`` polygon
    (``rec_polys``). Returns ``None`` for anything else - callers drop those, so a shape
    change degrades to "unmeasured" instead of raising mid-page.
    """
    flat = _flatten(value)
    if len(flat) not in (4, 8):
        return None
    xs, ys = flat[0::2], flat[1::2]
    return (min(xs), min(ys), max(xs), max(ys))


def _flip_y(box: Box, page_height: float) -> Box:
    return (box[0], page_height - box[3], box[2], page_height - box[1])


def _assign(cells: List[Box], boxes: List[Box]) -> Tuple[List[List[int]], int]:
    """Map each box to the first cell containing its centre; return (per-cell ids, unassigned)."""
    per_cell: List[List[int]] = [[] for _ in cells]
    unassigned = 0
    for idx, box in enumerate(boxes):
        cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
        for cell_idx, cell in enumerate(cells):
            if cell[0] <= cx <= cell[2] and cell[1] <= cy <= cell[3]:
                per_cell[cell_idx].append(idx)
                break
        else:
            unassigned += 1
    return per_cell, unassigned


def aggregate_cell_confidence(
    cell_boxes: Iterable[Any],
    rec_boxes: Iterable[Any],
    rec_scores: Iterable[Any],
    page_height: Optional[float],
    *,
    frame_ok_ratio: float = DEFAULT_FRAME_OK_RATIO,
) -> Dict[str, Any]:
    """Per-cell confidence for one table, aligned with ``cell_boxes`` order.

    Returns ``{cells, frame, hits, unassigned, n_rec, n_cells, measured, reason}`` where
    ``cells[i]`` is the min ``rec_score`` of the entries whose centre falls in cell ``i``
    (``None`` when the cell has no entry), ``frame`` is ``"raw"`` / ``"flip"`` / ``None``,
    and ``measured=False`` means the whole table must be reported unmeasured. ``reason`` is
    one of ``ok`` / ``no_cells`` / ``no_entries`` / ``frame_unresolved``.

    The frame is picked by containment (a tie keeps ``raw``); the flipped candidate is only
    considered when ``page_height`` is a usable positive number.
    """
    cells = [b for b in (as_box(c) for c in cell_boxes) if b is not None]

    pairs: List[Tuple[Box, float]] = []
    for raw, score in zip(rec_boxes, rec_scores):
        box = as_box(raw)
        if box is None:
            continue
        try:
            pairs.append((box, float(score)))
        except (TypeError, ValueError):
            continue

    n_rec, n_cells = len(pairs), len(cells)
    result: Dict[str, Any] = {
        "cells": [None] * n_cells,
        "frame": None,
        "hits": 0,
        "unassigned": 0,
        "n_rec": n_rec,
        "n_cells": n_cells,
        "measured": False,
        "reason": "ok",
    }
    if not n_cells:
        result["reason"] = "no_cells"
        return result
    if not n_rec:
        result["reason"] = "no_entries"
        return result

    try:
        height = float(page_height) if page_height is not None else 0.0
    except (TypeError, ValueError):
        height = 0.0

    candidates = [("raw", [box for box, _ in pairs])]
    if height > 0:
        candidates.append(("flip", [_flip_y(box, height) for box, _ in pairs]))

    best_frame, best_hits, best_per_cell, best_unassigned = "raw", -1, None, n_rec
    for frame, boxes in candidates:
        per_cell, unassigned = _assign(cells, boxes)
        hits = n_rec - unassigned
        if hits > best_hits:  # ties keep the earlier (raw) candidate
            best_frame, best_hits, best_per_cell, best_unassigned = frame, hits, per_cell, unassigned

    result.update(frame=best_frame, hits=best_hits, unassigned=best_unassigned)
    if best_hits < frame_ok_ratio * n_rec:
        result["frame"] = None
        result["reason"] = "frame_unresolved"
        return result

    assert best_per_cell is not None  # set whenever n_rec > 0
    for cell_idx, entry_ids in enumerate(best_per_cell):
        if entry_ids:
            result["cells"][cell_idx] = round(min(pairs[i][1] for i in entry_ids), 6)
    result["measured"] = True
    return result
