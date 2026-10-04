"""Per-table layout model (F1 split from ``table_alignment.py`` - P-028 PR1).

Pure move, zero behavior change (D2): the ``W_*`` word-tuple index constants,
the P-002 C2 geometry constants, the row/column cluster dataclasses and
:func:`build_layout_model` live here; ``table_alignment.py`` imports them back
(one-way, alignment -> layout, no cycle).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# fitz get_text("words") tuple indices (R5: list-or-tuple, index access)
W_X0, W_Y0, W_X1, W_Y1 = 0, 1, 2, 3
W_TEXT, W_BLOCK, W_LINE, W_WORDNO = 4, 5, 6, 7


def _median(values: List[float]) -> float:
    """Deterministic median (lower element for even counts)."""
    s = sorted(values)
    if not s:
        return 0.0
    return s[(len(s) - 1) // 2]


# --- P-002 C2: geometry constants (C0③ approved 2026-09-29, R1 red line) ---
# EXP_X_MIN_RATIO was calibrated 0.15 -> 0.05 against the mamba p29/p34 layout
# dumps (0.15 x table width zero-anchored 2-5 columns on narrow-column tables).
NEIGHBORHOOD_PAD_PT = 8.0
T1_MAX_RUN_WORDS = 4  # max consecutive words in one (block, line) window
ROW_TOL_FLOOR_PT = 2.0
ROW_TOL_RATIO = 0.5  # x h_med (median neighborhood word height)
COL_GAP_PT = 6.0
EXP_X_MIN_RATIO = 0.05  # x table width pt
EXP_X_COL_RATIO = 0.6  # x uniform column width pt


@dataclass
class RowCluster:
    """Greedy y1 cluster of neighborhood words (P-002 §3.5.0 step 1)."""

    words: List[Any]
    y0: float
    y1: float
    vision_row: Optional[int]


@dataclass
class ColGroup:
    """In-row word group split on x gaps (§3.5.0 step 3) + column assignment."""

    words: List[Any]
    x0: float
    x1: float
    center: float
    assigned_col: Optional[int]


@dataclass
class LayoutModel:
    """Per-table layout model (P-002 §3.3.1-b, built once per table).

    ``neighborhood_words`` (bbox padded by NEIGHBORHOOD_PAD_PT, minus words
    centered inside any sibling table) drive clustering / T1 / column
    assignment; ``in_bbox_words`` (unexpanded) is the T3 word source.
    ``word_index`` maps id(word) -> (row cluster idx, col group idx).
    """

    neighborhood_words: List[Any]
    in_bbox_words: List[Any]
    row_clusters: List[RowCluster]
    col_groups: List[List[ColGroup]]
    row_bands: List[Tuple[float, float]]
    col_bands: List[Tuple[float, float]]
    col_expanded: List[Tuple[float, float]]
    col_centers: List[float]
    h_med: float
    row_tol: float
    word_index: Dict[int, Tuple[int, int]]


def build_layout_model(
    table_bbox: Dict[str, Any],
    page_words: List[Any],
    n_rows: int,
    n_cols: int,
    sibling_bboxes: Optional[List[Tuple[float, float, float, float]]] = None,
) -> LayoutModel:
    """Build the per-table layout model (P-002 §3.3.1-b / §3.5.0).

    All geometry is pt (visual raster px / 2; missing bbox keys degrade to
    zeroes). Deterministic: every multi-candidate pick has an explicit
    tie-break (lower row/column index, no reliance on set order).
    """
    sibling_bboxes = sibling_bboxes or []
    bbox = table_bbox or {}
    tx = float(bbox.get("x", 0.0)) / 2.0
    ty = float(bbox.get("y", 0.0)) / 2.0
    tw = float(bbox.get("width", 0.0)) / 2.0
    th = float(bbox.get("height", 0.0)) / 2.0
    tb = (tx, ty, tx + tw, ty + th)
    nb = (
        tx - NEIGHBORHOOD_PAD_PT,
        ty - NEIGHBORHOOD_PAD_PT,
        tx + tw + NEIGHBORHOOD_PAD_PT,
        ty + th + NEIGHBORHOOD_PAD_PT,
    )

    def _center_in(w: Any, box: Tuple[float, float, float, float]) -> bool:
        cx = (float(w[W_X0]) + float(w[W_X1])) / 2.0
        cy = (float(w[W_Y0]) + float(w[W_Y1])) / 2.0
        return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]

    words = [w for w in page_words if isinstance(w, (list, tuple)) and len(w) >= 8]
    in_bbox_words = [w for w in words if _center_in(w, tb)]
    neighborhood = [
        w
        for w in words
        if _center_in(w, nb) and not any(_center_in(w, s) for s in sibling_bboxes)
    ]

    # (1) row clustering: greedy on ascending y1, split beyond ROW_TOL
    h_med = _median([float(w[W_Y1]) - float(w[W_Y0]) for w in neighborhood])
    row_tol = max(ROW_TOL_FLOOR_PT, ROW_TOL_RATIO * h_med)
    row_clusters: List[RowCluster] = []
    for w in sorted(neighborhood, key=lambda w: (float(w[W_Y1]), float(w[W_X0]))):
        y1 = float(w[W_Y1])
        if row_clusters and y1 - row_clusters[-1].y1 <= row_tol:
            c = row_clusters[-1]
            c.words.append(w)
            c.y0 = min(c.y0, float(w[W_Y0]))
            c.y1 = max(c.y1, y1)
        else:
            row_clusters.append(
                RowCluster(words=[w], y0=float(w[W_Y0]), y1=y1, vision_row=None)
            )

    # (2) uniform vision grid bands (same px/2 formula as derive_cell_bbox)
    row_bands = [(ty + i * th / n_rows, ty + (i + 1) * th / n_rows) for i in range(n_rows)]
    col_bands = [(tx + j * tw / n_cols, tx + (j + 1) * tw / n_cols) for j in range(n_cols)]
    exp_x = max(EXP_X_MIN_RATIO * tw, EXP_X_COL_RATIO * (tw / n_cols)) if n_cols else 0.0
    col_expanded = [(a - exp_x, b + exp_x) for (a, b) in col_bands]
    col_centers = [(a + b) / 2.0 for (a, b) in col_bands]

    # (3) cluster -> vision row: max band overlap, ties to the lower row index
    for c in row_clusters:
        best, best_len = None, -1.0
        for i, (a, b) in enumerate(row_bands):
            ov = min(c.y1, b) - max(c.y0, a)
            if ov > best_len:
                best, best_len = i, ov
        c.vision_row = best

    # (4) in-row word groups (x0 order, split on gap >= COL_GAP_PT), then
    #     group -> vision column: expanded window, nearest unexpanded center,
    #     ties to the lower column index; no window hit -> no assignment
    col_groups: List[List[ColGroup]] = []
    word_index: Dict[int, Tuple[int, int]] = {}
    for ridx, c in enumerate(row_clusters):
        groups: List[ColGroup] = []
        for w in sorted(c.words, key=lambda w: float(w[W_X0])):
            if groups and float(w[W_X0]) - groups[-1].x1 < COL_GAP_PT:
                g = groups[-1]
                g.words.append(w)
                g.x1 = max(g.x1, float(w[W_X1]))
            else:
                groups.append(
                    ColGroup(
                        words=[w],
                        x0=float(w[W_X0]),
                        x1=float(w[W_X1]),
                        center=0.0,
                        assigned_col=None,
                    )
                )
        for gidx, g in enumerate(groups):
            g.center = (g.x0 + g.x1) / 2.0
            cand = [
                j
                for j in range(n_cols)
                if col_expanded[j][0] <= g.center <= col_expanded[j][1]
            ]
            if cand:
                g.assigned_col = min(
                    cand, key=lambda j: (abs(col_centers[j] - g.center), j)
                )
            for w in g.words:
                word_index[id(w)] = (ridx, gidx)
        col_groups.append(groups)

    return LayoutModel(
        neighborhood_words=neighborhood,
        in_bbox_words=in_bbox_words,
        row_clusters=row_clusters,
        col_groups=col_groups,
        row_bands=row_bands,
        col_bands=col_bands,
        col_expanded=col_expanded,
        col_centers=col_centers,
        h_med=h_med,
        row_tol=row_tol,
        word_index=word_index,
    )
