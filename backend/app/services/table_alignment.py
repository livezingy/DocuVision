"""Three-layer cell alignment (P-002): value match -> geometric -> cluster.

New-code home per P-002 D1: the layout model, the T1/T3 solvers and the
backfill sanity gate live here, while ``table_backfill.py`` keeps its existing
funnel in place and imports from this module (one-way, backfill -> alignment).

C1 scope: the ``REASON_*`` contract constants and :func:`is_ocr_confusion`.
C2 scope: the pinned geometry constants (C0③ approved 2026-09-29),
:func:`build_layout_model` and the T1 anchored value match
(:func:`solve_t1` / :func:`resolve_t1_collision`). T3 lands in C3.

The C0 debug ``layout_preview`` was removed once calibration concluded: the
same statistics are recomputable offline from :func:`build_layout_model`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from docuvision_core.utils.pdf_text_utils import normalize_for_compare

from app.services.table_layout import (
    T1_MAX_RUN_WORDS, W_BLOCK, W_LINE, W_TEXT, W_WORDNO, W_X0, W_X1, W_Y0, W_Y1,  # 主模块 T1/T3 使用
    LayoutModel, build_layout_model,  # re-export：table_backfill 与测试路径稳定
)

# --- P-002 C1: reason contract (9 values, D2; P-028 adds band_range) -----
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
REASON_BAND_RANGE = "band_range_incomplete"

REASON_KEYS: Tuple[str, ...] = (
    REASON_VALUE_MATCH,
    REASON_GEO,
    REASON_CLUSTER,
    REASON_SANITY,
    REASON_NO_LINE,
    REASON_CROSSING,
    REASON_MULTI,
    REASON_SHAPE,
    REASON_BAND_RANGE,
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


class T1Status(str, Enum):
    """T1 outcome (P-002 §3.3.1-c): UNIQUE/COLLISION/NONE."""

    UNIQUE = "unique"
    COLLISION = "collision"
    NONE = "none"


@dataclass
class RunMatch:
    """One value-equal consecutive-word run (same block/line)."""

    words: List[Any]
    row_idx: int
    group_idx: int
    norm: str


def _drop_covered_runs(runs: List[RunMatch]) -> List[RunMatch]:
    """Drop runs fully covered by a longer run over the same words (§3.3)."""
    if len(runs) < 2:
        return runs
    id_sets = [frozenset(id(w) for w in r.words) for r in runs]
    kept = []
    for i, run in enumerate(runs):
        if not any(
            i != j and len(id_sets[i]) < len(id_sets[j]) and id_sets[i] <= id_sets[j]
            for j in range(len(runs))
        ):
            kept.append(run)
    return kept


def _gen_runs(model: LayoutModel, target: str) -> List[RunMatch]:
    """Consecutive 1..T1_MAX_RUN_WORDS word windows per (block, line) whose
    normalized join equals ``target``; covered short runs are dropped."""
    buckets: Dict[Tuple[Any, Any], List[Any]] = {}
    for w in model.neighborhood_words:
        buckets.setdefault((w[W_BLOCK], w[W_LINE]), []).append(w)
    runs: List[RunMatch] = []
    for ws in buckets.values():
        ws = sorted(ws, key=lambda w: w[W_WORDNO])
        for start in range(len(ws)):
            for end in range(start + 1, min(start + T1_MAX_RUN_WORDS, len(ws)) + 1):
                chunk = ws[start:end]
                if normalize_for_compare(" ".join(str(w[W_TEXT]) for w in chunk)) == target:
                    ridx, gidx = model.word_index[id(chunk[0])]
                    runs.append(
                        RunMatch(words=chunk, row_idx=ridx, group_idx=gidx, norm=target)
                    )
    return _drop_covered_runs(runs)


def solve_t1(
    model: LayoutModel,
    ocr_text: str,
    cell_row: int,
    cell_col: int,
) -> Tuple[T1Status, Optional[List[Any]]]:
    """Row-band + column-window anchored value match (P-002 §3.3, T1).

    Candidate runs: normalized join equal to the OCR value AND clustered into
    vision row ``cell_row``. 0 runs -> NONE; 1 run -> UNIQUE only when its
    word group is assigned to ``cell_col`` (else NONE); >= 2 -> COLLISION
    (caller then tries :func:`resolve_t1_collision`; failure falls to T2).
    UNIQUE returns the matched words — equal by construction, so the outcome
    is green (``text_confirmed`` / ``value_match``) and ``data`` is untouched.
    """
    target = normalize_for_compare(ocr_text)
    if not target:
        return T1Status.NONE, None
    runs = [
        r
        for r in _gen_runs(model, target)
        if model.row_clusters[r.row_idx].vision_row == cell_row
    ]
    if not runs:
        return T1Status.NONE, None
    if len(runs) == 1:
        group = model.col_groups[runs[0].row_idx][runs[0].group_idx]
        if group.assigned_col == cell_col:
            return T1Status.UNIQUE, runs[0].words
        return T1Status.NONE, None
    return T1Status.COLLISION, None


def resolve_t1_collision(
    model: LayoutModel,
    ocr_text: str,
    cell_row: int,
    cell_col: int,
) -> Tuple[bool, Optional[List[Any]]]:
    """Resolve a same-row same-value T1 collision via the column window
    (P-002 §3.3 step 5): keep runs whose word group is assigned to
    ``cell_col``, then win only with the strictly closest unexpanded column
    center; 0 or tied candidates return ``(False, None)`` (fall to T2)."""
    target = normalize_for_compare(ocr_text)
    runs = [
        r
        for r in _gen_runs(model, target)
        if model.row_clusters[r.row_idx].vision_row == cell_row
    ]
    anchored = []
    for r in runs:
        group = model.col_groups[r.row_idx][r.group_idx]
        if group.assigned_col == cell_col:
            anchored.append(
                (abs(group.center - model.col_centers[cell_col]), r.group_idx, r)
            )
    if not anchored:
        return False, None
    anchored.sort(key=lambda t: (t[0], t[1]))
    if len(anchored) == 1 or anchored[0][0] < anchored[1][0]:
        return True, anchored[0][2].words
    return False, None


# --- P-002 C3: T3 text-cluster mapping (§3.5.1/§3.5.2) --------------------
# Provenance literals match table_backfill.PROVENANCE_TEXT_* (no circular import; tested).
PROVENANCE_CONFIRMED_LITERAL = "text_confirmed"
PROVENANCE_BACKFILLED_LITERAL = "text_backfilled"
PROVENANCE_MISMATCH_LITERAL = "text_mismatch"


def collect_t3_words(
    model: LayoutModel,
    cell_row: int,
    cell_col: int,
) -> List[Any]:
    """Words of the row-``cell_row`` clusters' column-``cell_col`` groups,
    restricted to the unexpanded in-bbox word set (§3.5.1); sorted by
    (cluster y1, word x0). Unassigned groups are skipped."""
    in_bbox_ids = {id(w) for w in model.in_bbox_words}
    words: List[Any] = []
    for ridx, cluster in enumerate(model.row_clusters):
        if cluster.vision_row != cell_row:
            continue
        for group in model.col_groups[ridx]:
            if group.assigned_col != cell_col:
                continue
            words.extend(w for w in group.words if id(w) in in_bbox_ids)
    words.sort(
        key=lambda w: (
            model.row_clusters[model.word_index[id(w)][0]].y1,
            float(w[W_X0]),
        )
    )
    return words


def solve_t3(
    model: LayoutModel,
    ocr_text: str,
    cell_row: int,
    cell_col: int,
    t2_fail_reason: str,
) -> Tuple[str, str, Optional[List[Any]]]:
    """T3 text-cluster solve (P-002 §3.5.1): join the row-i / column-j word
    set. Equal -> confirmed/cluster; confusion shape -> backfilled/cluster
    (sanity-gated); otherwise mismatch/sanity_reject, data untouched. An
    empty/whitespace word set -> (mismatch, ``t2_fail_reason``, None) — the
    honest red keeps the T2 failure reason."""
    words = collect_t3_words(model, cell_row, cell_col)
    if not words:
        return (PROVENANCE_MISMATCH_LITERAL, t2_fail_reason, None)
    tl_norm = normalize_for_compare(" ".join(str(w[W_TEXT]) for w in words))
    if not tl_norm:
        return (PROVENANCE_MISMATCH_LITERAL, t2_fail_reason, None)
    vis_norm = normalize_for_compare(ocr_text)
    if vis_norm == tl_norm:
        return (PROVENANCE_CONFIRMED_LITERAL, REASON_CLUSTER, words)
    if is_ocr_confusion(vis_norm, tl_norm):
        return (PROVENANCE_BACKFILLED_LITERAL, REASON_CLUSTER, words)
    return (PROVENANCE_MISMATCH_LITERAL, REASON_SANITY, words)


