"""Box geometry primitives (shared leaf #5, P-038 ruling A+ 2026-10-25).

The seven pure geometry helpers moved verbatim from ``figure_service.py``
(bbox dict -> tuple conversion, clamp, horizontal/vertical overlap ratios,
merge, containment, vertical gap) — zero outbound imports, no state, no
domain semantics beyond the layout bbox dict shape ("x/y/width/height").
``figure_service`` re-exports them (its internal call sites are unchanged);
``table_pseudo_filter`` imports them directly — the frozen ``table->figure``
edge dissolves (ratchet 5 -> 4). Underscore names preserved verbatim
(tier A); the naming heritage note: they were figure-private before the move.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

def _bbox_tuple(elem: Dict[str, Any]) -> Tuple[float, float, float, float]:
    b = elem.get("bbox") or {}
    x = float(b.get("x", 0) or 0)
    y = float(b.get("y", 0) or 0)
    w = float(b.get("width", 0) or 0)
    h = float(b.get("height", 0) or 0)
    return x, y, x + w, y + h


def _clamp_box(
    box: Tuple[float, float, float, float],
    width: int,
    height: int,
) -> Tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    x1 = max(0.0, min(x1, width))
    y1 = max(0.0, min(y1, height))
    x2 = max(0.0, min(x2, width))
    y2 = max(0.0, min(y2, height))
    return x1, y1, x2, y2


# ---------------------------------------------------------------------------
# Integrity checks — pure geometry, unit-testable without any image I/O.
# ---------------------------------------------------------------------------

def _h_overlap_ratio(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    overlap = min(a[2], b[2]) - max(a[0], b[0])
    if overlap <= 0:
        return 0.0
    ref = min(a[2] - a[0], b[2] - b[0])
    return overlap / ref if ref > 0 else 0.0


def _v_overlap_ratio(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    if overlap <= 0:
        return 0.0
    ref = min(a[3] - a[1], b[3] - b[1])
    return overlap / ref if ref > 0 else 0.0


def _merged_box(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def _containment_ratio(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    """Fraction of b's area covered by a (1.0 = b fully inside a)."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area_b = max(0.0, (b[2] - b[0]) * (b[3] - b[1]))
    return inter / area_b if area_b > 0 else 0.0


def _v_gap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    """Absolute vertical gap between two boxes (0 if overlapping, positive if apart)."""
    return max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
