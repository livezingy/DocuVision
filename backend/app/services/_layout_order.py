"""Reading-order helpers for layout elements (pure, no Paddle deps).

Why a separate module
---------------------
``layout_service.py`` imports ``paddle`` / ``cv2`` at module top, so it cannot
be loaded in the local Python env (no GPU stack). The reading-order sort
decision is pure logic and is the core of F1 (use PP-StructureV3
``block_order`` instead of naive ``(y, x)``). Extracting it here keeps it
unit-testable locally without any model imports.

Official basis
--------------
``parsing_res_list`` list order IS the reading order (Enhanced XYCut), and each
block carries a ``block_order`` field:
- PaddleOCR PP-StructureV3 docs
  https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md
- PaddleX example output (block_id / block_order)
  https://paddlepaddle.github.io/PaddleX/3.3/en/pipeline_usage/tutorials/ocr_pipelines/PP-StructureV3.html
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def reading_order_sort_key(elem: Dict[str, Any]) -> Tuple[int, Any]:
    """Sort key preferring ``reading_order`` (from PP-StructureV3 ``block_order``).

    Elements with a non-null ``reading_order`` sort first by that order.
    Elements without it fall back to ``(y, x)`` bbox ordering.

    Returns a tuple ``(group, ...)`` so elements with reading_order (group 0)
    always precede fallback elements (group 1), keeping the two groups stable.
    """
    ro = elem.get("reading_order")
    if ro is not None:
        try:
            return (0, int(ro))
        except (TypeError, ValueError):
            return (0, 0)
    bbox = elem.get("bbox", {}) or {}
    try:
        y = float(bbox.get("y", 0) or 0)
        x = float(bbox.get("x", 0) or 0)
    except (TypeError, ValueError):
        y, x = 0.0, 0.0
    return (1, y, x)


def sort_elements_by_reading_order(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a new list sorted by reading order (with ``(y, x)`` fallback).

    See ``reading_order_sort_key`` for the mixed-case policy.
    """
    return sorted(elements, key=reading_order_sort_key)


def has_reading_order(elements: List[Dict[str, Any]]) -> bool:
    """True if at least one element carries a non-null ``reading_order``."""
    return any(e.get("reading_order") is not None for e in elements)
