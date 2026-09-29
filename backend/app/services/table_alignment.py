"""Three-layer cell alignment helpers (P-002): value match -> geometric -> cluster.

New-code home per P-002 D1: the layout model, the T1/T3 solvers and the
backfill sanity gate live here, while ``table_backfill.py`` keeps its existing
funnel in place and imports from this module (one-way, backfill -> alignment).

C0 scope: the debug-only :func:`layout_preview` used to calibrate the geometry
constants (neighborhood pad / row tolerance / column gap / column expansion)
against real samples. C1 scope: the ``REASON_*`` contract constants and the
:func:`is_ocr_confusion` sanity gate. The solvers land in C2-C3; the constants
stay function parameters with proposed defaults until Ying approves the
calibrated values (P-002 R1) and are then pinned as module constants.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# fitz get_text("words") tuple indices (R5: list-or-tuple, index access)
W_X0, W_Y0, W_X1, W_Y1 = 0, 1, 2, 3
W_TEXT, W_BLOCK, W_LINE, W_WORDNO = 4, 5, 6, 7

# --- P-002 C1: reason contract (8 values, D2) ---------------------------
# Spec provenance-review.md §5 pins 6 values; "cluster" and "sanity_reject"
# extend it because the three-layer pipeline has two outcomes the 6-value
# enum cannot express (P-002 §4): a T3-resolved cell, and an alignment that
# succeeded but was rejected by the sanity gate.
REASON_VALUE_MATCH = "value_match"
REASON_GEO = "geometric"
REASON_CLUSTER = "cluster"
REASON_SANITY = "sanity_reject"
REASON_NO_LINE = "no_aligned_line"
REASON_CROSSING = "crossing"
REASON_MULTI = "multi_line"
REASON_SHAPE = "shape_mismatch"

REASON_KEYS: Tuple[str, ...] = (
    REASON_VALUE_MATCH,
    REASON_GEO,
    REASON_CLUSTER,
    REASON_SANITY,
    REASON_NO_LINE,
    REASON_CROSSING,
    REASON_MULTI,
    REASON_SHAPE,
)

# --- P-002 C1: backfill sanity gate (spec provenance-review.md §4.2) ----
# Bidirectional OCR misread pairs; a differing character pair passes only
# when both directions are listed.
_OCR_CONFUSION_NEIGHBORS = {
    "0": frozenset("Oo"),
    "O": frozenset("0"),
    "o": frozenset("0"),
    "1": frozenset("lIi"),
    "l": frozenset("1"),
    "I": frozenset("1"),
    "i": frozenset("1"),
    "5": frozenset("Ss"),
    "S": frozenset("5"),
    "s": frozenset("5"),
    "8": frozenset("B"),
    "B": frozenset("8"),
    "6": frozenset("bG"),
    "b": frozenset("6"),
    "G": frozenset("6"),
    "9": frozenset("gq"),
    "g": frozenset("9"),
    "q": frozenset("9"),
    "2": frozenset("Zz"),
    "Z": frozenset("2"),
    "z": frozenset("2"),
    "✓": frozenset("√"),
    "√": frozenset("✓"),
    "●": frozenset("•"),
    "•": frozenset("●"),
    "×": frozenset("x"),
    "x": frozenset("×"),
}


def _replacement_cap(length: int) -> int:
    return 1 if length <= 6 else 2


def _within_confusion_budget(a: str, b: str, limit: int) -> bool:
    """Positional compare: equal chars pass, differing chars must hit a
    bidirectional confusion pair, and replacements stay within ``limit``."""
    mismatches = 0
    for ca, cb in zip(a, b):
        if ca == cb:
            continue
        if cb not in _OCR_CONFUSION_NEIGHBORS.get(ca, frozenset()):
            return False
        mismatches += 1
        if mismatches > limit:
            return False
    return True


def is_ocr_confusion(a: str, b: str) -> bool:
    """Sanity gate for the amber (backfill) branch (P-002 §3.2).

    ``a`` is the OCR value, ``b`` the text-layer value, both already passed
    through ``normalize_for_compare`` (the caller guarantees it — single
    import source, R9). True only when they plausibly read the same:

    1. length difference <= 1;
    2. every differing character pair is a bidirectional OCR confusion pair;
    3. replacements within the cap — length <= 6 allows 1, length > 6 allows
       2, the threshold taken on the longer string.

    With a length difference of 1, drop-tail alignment is tried before
    drop-head (first passing branch wins; the dropped character is not
    counted as a replacement). Empty inputs never pass — any doubt keeps the
    vision result.
    """
    if not a or not b:
        return False
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return _within_confusion_budget(a, b, _replacement_cap(len(a)))
    long_s, short_s = (a, b) if len(a) > len(b) else (b, a)
    cap = _replacement_cap(len(long_s))
    if _within_confusion_budget(long_s[:-1], short_s, cap):
        return True
    return _within_confusion_budget(long_s[1:], short_s, cap)


def _median(values: List[float]) -> float:
    """Deterministic median (lower element for even counts)."""
    s = sorted(values)
    if not s:
        return 0.0
    return s[(len(s) - 1) // 2]


def layout_preview(
    table: Dict[str, Any],
    page_words: List[Any],
    sibling_bboxes: Optional[List[Tuple[float, float, float, float]]] = None,
    *,
    neighborhood_pad_pt: float = 8.0,
    row_tol_floor_pt: float = 2.0,
    row_tol_ratio: float = 0.5,
    col_gap_pt: float = 6.0,
    exp_x_min_ratio: float = 0.15,
    exp_x_col_ratio: float = 0.6,
) -> Dict[str, Any]:
    """Debug-only layout statistics for one table (P-002 C0 calibration).

    Mirrors the planned ``build_layout_model`` steps (§3.5.0: neighborhood
    selection, y1 row clustering, in-row word grouping, column-window
    assignment) with the proposed constant defaults, and dumps the underlying
    gap distributions so the constants can be calibrated against real samples
    before they are pinned. Never called outside DEBUG_MODE; produces no
    product behavior.
    """
    sibling_bboxes = sibling_bboxes or []
    data = table.get("data")
    rows = data if isinstance(data, list) else []
    n_rows = len(rows)
    n_cols = max((len(r) for r in rows if isinstance(r, list)), default=0)
    bbox = table.get("bbox") or {}
    tx = float(bbox.get("x", 0.0)) / 2.0
    ty = float(bbox.get("y", 0.0)) / 2.0
    tw = float(bbox.get("width", 0.0)) / 2.0
    th = float(bbox.get("height", 0.0)) / 2.0
    tb = (tx, ty, tx + tw, ty + th)
    nb = (
        tx - neighborhood_pad_pt,
        ty - neighborhood_pad_pt,
        tx + tw + neighborhood_pad_pt,
        ty + th + neighborhood_pad_pt,
    )

    def _cx(w: Any) -> float:
        return (float(w[W_X0]) + float(w[W_X1])) / 2.0

    def _cy(w: Any) -> float:
        return (float(w[W_Y0]) + float(w[W_Y1])) / 2.0

    def _center_in(w: Any, box: Tuple[float, float, float, float]) -> bool:
        return box[0] <= _cx(w) <= box[2] and box[1] <= _cy(w) <= box[3]

    words = [
        w for w in page_words if isinstance(w, (list, tuple)) and len(w) >= 8
    ]
    in_bbox_words = [w for w in words if _center_in(w, tb)]
    neighborhood = [
        w
        for w in words
        if _center_in(w, nb)
        and not any(_center_in(w, s) for s in sibling_bboxes)
    ]

    heights = [float(w[W_Y1]) - float(w[W_Y0]) for w in neighborhood]
    h_med = _median(heights)
    row_tol = max(row_tol_floor_pt, row_tol_ratio * h_med)

    # Row clustering (greedy on ascending y1, tolerance vs current cluster y1)
    y1_gaps: List[float] = []
    clusters: List[Dict[str, Any]] = []
    for w in sorted(neighborhood, key=lambda w: (float(w[W_Y1]), float(w[W_X0]))):
        y1 = float(w[W_Y1])
        if clusters:
            y1_gaps.append(round(y1 - clusters[-1]["y1"], 2))
        if clusters and y1 - clusters[-1]["y1"] <= row_tol:
            c = clusters[-1]
            c["words"].append(w)
            c["y0"] = min(c["y0"], float(w[W_Y0]))
            c["y1"] = max(c["y1"], y1)
        else:
            clusters.append({"y0": float(w[W_Y0]), "y1": y1, "words": [w]})

    # Cluster -> vision row (max band overlap, ties to the lower row index)
    row_bands = [
        (ty + i * th / n_rows, ty + (i + 1) * th / n_rows)
        for i in range(n_rows)
    ] if n_rows > 0 and th > 0 else []
    mapped_rows = set()
    for c in clusters:
        best, best_len = None, -1.0
        for i, (a, b) in enumerate(row_bands):
            ov = min(c["y1"], b) - max(c["y0"], a)
            if ov > best_len:
                best, best_len = i, ov
        if best is not None:
            mapped_rows.add(best)

    # In-row word groups (x0 order, split on gap >= col_gap) + column windows
    exp_x = (
        max(exp_x_min_ratio * tw, exp_x_col_ratio * (tw / n_cols))
        if n_cols > 0 and tw > 0
        else 0.0
    )
    col_width = tw / n_cols if n_cols else 0.0
    col_centers = [tx + (j + 0.5) * col_width for j in range(n_cols)]
    x_gaps: List[float] = []
    groups_total = 0
    groups_assigned = 0
    assign_counts = [0] * n_cols
    for c in clusters:
        ws = sorted(c["words"], key=lambda w: float(w[W_X0]))
        groups: List[Dict[str, Any]] = []
        for w in ws:
            if groups and float(w[W_X0]) - groups[-1]["x1"] < col_gap_pt:
                g = groups[-1]
                g["words"].append(w)
                g["x1"] = max(g["x1"], float(w[W_X1]))
            else:
                groups.append(
                    {"words": [w], "x0": float(w[W_X0]), "x1": float(w[W_X1])}
                )
        for prev, cur in zip(ws, ws[1:]):
            x_gaps.append(round(float(cur[W_X0]) - float(prev[W_X1]), 2))
        groups_total += len(groups)
        for g in groups:
            center = (g["x0"] + g["x1"]) / 2.0
            cand = [
                j
                for j in range(n_cols)
                if tx + j * col_width - exp_x
                <= center
                <= tx + (j + 1) * col_width + exp_x
            ]
            if cand:
                groups_assigned += 1
                j = min(cand, key=lambda jj: (abs(col_centers[jj] - center), jj))
                assign_counts[j] += 1

    outside = [w for w in neighborhood if not _center_in(w, tb)]
    outside_max = max(
        (
            max(tb[0] - _cx(w), _cx(w) - tb[2], tb[1] - _cy(w), _cy(w) - tb[3])
            for w in outside
        ),
        default=0.0,
    )
    return {
        "table_id": table.get("id"),
        "n_rows": n_rows,
        "n_cols": n_cols,
        "table_bbox_pt": [round(v, 2) for v in tb],
        "neighborhood_words": len(neighborhood),
        "words_in_bbox": len(in_bbox_words),
        "neighborhood_outside_bbox": len(outside),
        "outside_max_pt": round(outside_max, 2),
        "word_h_median_pt": round(h_med, 2),
        "row_tol_proposed_pt": round(row_tol, 2),
        "row_y1_gaps_sorted_pt": sorted(y1_gaps),
        "row_clusters": len(clusters),
        "vision_rows_covered": len(mapped_rows),
        "in_row_x_gaps_sorted_pt": sorted(x_gaps),
        "col_gap_proposed_pt": col_gap_pt,
        "col_groups": groups_total,
        "uniform_col_width_pt": round(col_width, 2),
        "exp_x_proposed_pt": round(exp_x, 2),
        "col_group_assign_hit_ratio": (
            round(groups_assigned / groups_total, 3) if groups_total else 0.0
        ),
        "col_group_assign_counts": assign_counts,
    }
