"""Figure split/caption heuristics — pure layout-element geometry checks.

Split from the former figure_service.py monolith (S1 batch 9): label
constants, caption binding and the split/bbox-space warning heuristics —
zero IO and zero image libraries (geometry primitives come from the
bbox_geometry shared leaf). The crop/IO side stays in figure_service, which
re-exports the names below for the existing test import surface.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.services.bbox_geometry import (
    _bbox_tuple,
    _containment_ratio,
    _h_overlap_ratio,
    _merged_box,
    _v_gap,
    _v_overlap_ratio,
)


# Region labels treated as croppable figures. Mirrors envelope_builder
# _VISION_BLOCK_LABELS plus the flowchart label produced by the layout
# service. "seal" is intentionally excluded (seal_service owns seals).
FIGURE_LABELS: frozenset = frozenset(
    {
        "figure",
        "image",
        "chart",
        "figure_table_chart",
        "picture",
        "flowchart",
    }
)

# Layout labels treated as captions that can be bound to nearby
# figure/table regions. Mirrors PP-DocLayout-L categories (F2) and
# envelope_builder _TEXT_BLOCK_LABELS caption subset.
CAPTION_LABELS: frozenset = frozenset(
    {
        "figure_caption",
        "figure_title",
        "figure_table_chart_title",
    }
)

TABLE_CAPTION_LABELS: frozenset = frozenset(
    {
        "table_caption",
        "figure_table_chart_title",
    }
)

# Minimum crop size (px). Smaller boxes are almost always noise.
MIN_CROP_PX = 8


def _figure_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Select layout elements whose type maps to a figure region."""
    out: List[Dict[str, Any]] = []
    for elem in elements or []:
        etype = str(elem.get("type") or "").lower().strip()
        if etype in FIGURE_LABELS:
            out.append(elem)
    return out


def _caption_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Select layout elements whose type maps to a figure caption."""
    out: List[Dict[str, Any]] = []
    for elem in elements or []:
        etype = str(elem.get("type") or "").lower().strip()
        if etype in CAPTION_LABELS:
            out.append(elem)
    return out




def _bind_captions(
    figures: List[Dict[str, Any]],
    all_elements: List[Dict[str, Any]],
    *,
    h_overlap_min: float = 0.5,
    v_gap_max_ratio: float = 0.5,
) -> None:
    """Bind caption elements to nearby figure/table regions in-place.

    Simplified reimplementation of PaddleX ``update_vision_child_blocks``
    (PaddleOCR 3.0 Report §3). For each figure, find the nearest caption
    element on the same page that satisfies:
    - horizontal overlap >= ``h_overlap_min`` (caption horizontally
      overlaps the figure region)
    - vertical gap < ``v_gap_max_ratio`` * max(figure_height, caption_height)
      (caption is close to the figure, above or below)

    The caption text and id are written to the figure dict as
    ``caption`` and ``caption_id``.

    A caption is consumed by the first figure that binds it; subsequent
    figures will not reuse it (one-to-one binding).
    """
    captions = _caption_elements(all_elements)
    if not captions or not figures:
        return

    consumed: set = set()
    for fig in figures:
        fig_page = int(fig.get("page", 1) or 1)
        fig_box = _bbox_tuple(fig)
        fig_h = fig_box[3] - fig_box[1]
        best_caption = None
        best_gap = float("inf")

        for cap in captions:
            cap_id = cap.get("id")
            if cap_id in consumed:
                continue
            if int(cap.get("page", 1) or 1) != fig_page:
                continue
            cap_box = _bbox_tuple(cap)
            if _h_overlap_ratio(fig_box, cap_box) < h_overlap_min:
                continue
            gap = _v_gap(fig_box, cap_box)
            cap_h = cap_box[3] - cap_box[1]
            threshold = v_gap_max_ratio * max(fig_h, cap_h) if max(fig_h, cap_h) > 0 else 50.0
            if gap > threshold:
                continue
            if gap < best_gap:
                best_gap = gap
                best_caption = cap

        if best_caption is not None:
            consumed.add(best_caption.get("id"))
            fig["caption"] = best_caption.get("text") or ""
            fig["caption_id"] = best_caption.get("id")


def _distinct_bound_captions(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """True when two figures already bound different captions (independent figs)."""
    id_a = str(a.get("caption_id") or "").strip()
    id_b = str(b.get("caption_id") or "").strip()
    if id_a and id_b and id_a != id_b:
        return True
    cap_a = str(a.get("caption") or "").strip()
    cap_b = str(b.get("caption") or "").strip()
    return bool(cap_a and cap_b and cap_a != cap_b)


# Stacked/side-by-side regions taller than this fraction of the page, with a
# real gap (not NMS overlap), are treated as complete figures — not halves.
COMPLETE_FIG_H_RATIO = 0.20


def _both_complete_looking(
    box_a: Tuple[float, float, float, float],
    box_b: Tuple[float, float, float, float],
    page_height: float,
) -> bool:
    if page_height <= 0:
        return False
    min_h = page_height * COMPLETE_FIG_H_RATIO
    return (box_a[3] - box_a[1]) >= min_h and (box_b[3] - box_b[1]) >= min_h


def detect_split_warnings(
    figure_boxes: List[Dict[str, Any]],
    page_height: float,
) -> List[Dict[str, Any]]:
    """Detect figure regions that the layout detector likely split apart.

    Heuristics (per page, pairwise):
    - vertical split: two boxes stacked (small gap OR small overlap — NMS
    splits produce both) with strong horizontal overlap.
    - horizontal split: two boxes side-by-side with small gap and strong
    vertical overlap.
    - nested_regions: one box almost fully contains the other (info-level;
    often a caption box inside a figure).

    Independent figures are not merged when they already have distinct
    bound captions, or when a vertical pair both look complete (height
    >= 20% of page) and are separated by a real gap (not NMS overlap).

    Args:
        figure_boxes: list of {"id", "page", "bbox": {x,y,width,height}}
        page_height: height of the analyzed raster, used for gap thresholds.

    Returns:
        Warnings: [{"kind", "page", "ids", "merged_bbox": {x,y,width,height}}]
    """
    warnings: List[Dict[str, Any]] = []
    by_page: Dict[int, List[Dict[str, Any]]] = {}
    for item in figure_boxes:
        by_page.setdefault(int(item.get("page", 1) or 1), []).append(item)

    gap_limit = max(12.0, page_height * 0.04) if page_height > 0 else 12.0

    for page, items in by_page.items():
        n = len(items)
        if n < 2:
            continue
        boxes = [(item.get("id", ""), _bbox_tuple(item)) for item in items]
        for i in range(n):
            for j in range(i + 1, n):
                id_a, box_a = boxes[i]
                id_b, box_b = boxes[j]
                kind = None
                v_gap = 0.0
                h_gap = 0.0
                # Containment first: a caption/inner box inside a figure is
                # nesting, not a split.
                if (
                    _containment_ratio(box_a, box_b) >= 0.9
                    or _containment_ratio(box_b, box_a) >= 0.9
                ):
                    kind = "nested_regions"
                else:
                    # vertical adjacency: a above b (gap >= 0) or slight
                    # overlap (NMS split artefact, gap < 0 but shallow).
                    v_gap = box_b[1] - box_a[3]
                    min_h = min(box_a[3] - box_a[1], box_b[3] - box_b[1])
                    overlap_limit = min_h * 0.5
                    if (
                        _h_overlap_ratio(box_a, box_b) >= 0.6
                        and (0 <= v_gap <= gap_limit or -overlap_limit <= v_gap < 0)
                    ):
                        kind = "possible_vertical_split"
                    if kind is None:
                        # horizontal adjacency: a left of b.
                        h_gap = box_b[0] - box_a[2]
                        if (
                            _v_overlap_ratio(box_a, box_b) >= 0.6
                            and 0 <= h_gap <= gap_limit
                        ):
                            kind = "possible_horizontal_split"
                if kind in {"possible_vertical_split", "possible_horizontal_split"}:
                    item_a = items[i]
                    item_b = items[j]
                    if _distinct_bound_captions(item_a, item_b):
                        kind = None
                    elif (
                        kind == "possible_vertical_split"
                        and v_gap >= 0
                        and _both_complete_looking(box_a, box_b, page_height)
                    ):
                        kind = None
                if kind:
                    m = _merged_box(box_a, box_b)
                    warnings.append(
                        {
                            "kind": kind,
                            "page": page,
                            "ids": [id_a, id_b],
                            "merged_bbox": {
                                "x": round(m[0], 1),
                                "y": round(m[1], 1),
                                "width": round(m[2] - m[0], 1),
                                "height": round(m[3] - m[1], 1),
                            },
                        }
                    )
    return warnings


def _detect_bbox_space_mismatch(
    figures: List[Dict[str, Any]],
    pages: Dict[int, Tuple[Any, int, int]],
    *,
    tolerance_px: float = 3.0,
) -> List[Dict[str, Any]]:
    """Detect figure bboxes that exceed the rendered raster dimensions.

    A bbox whose max x/y is larger than the page raster (beyond a small
    tolerance) indicates the bbox lives in a different coordinate space
    than the crop raster -- e.g. PPStructureV3 returned preprocessed-space
    (rotated/unwarped) boxes while cropping uses the un-rotated 2x raster.
    This is the leading cause of "all figures show the same wrong image":
    the wrong-space bbox maps to a fixed region across pages.

    Returns:
        Warnings: [{"kind", "page", "id", "bbox_max", "raster": {width,height}}]
    """
    warnings: List[Dict[str, Any]] = []
    for fig in figures:
        page_no = int(fig.get("page", 1) or 1)
        source = pages.get(page_no)
        if source is None:
            # Reported separately as a per-figure error in crop_figures.
            continue
        _, width, height = source
        x1, y1, x2, y2 = _bbox_tuple(fig)
        over_w = x2 > width + tolerance_px
        over_h = y2 > height + tolerance_px
        # Swapped-dims signal: width/height of bbox exceed raster in one
        # axis but fit the other -- typical of a 90-degree rotation.
        swapped = (over_w and y2 <= height + tolerance_px) or (
            over_h and x2 <= width + tolerance_px
        )
        if over_w or over_h:
            warnings.append(
                {
                    "kind": "bbox_space_mismatch",
                    "page": page_no,
                    "id": fig.get("id"),
                    "bbox": fig.get("bbox"),
                    "bbox_max": {"x": round(x2, 1), "y": round(y2, 1)},
                    "raster": {"width": int(width), "height": int(height)},
                    "over_w": bool(over_w),
                    "over_h": bool(over_h),
                    "swapped_dims": bool(swapped),
                }
            )
    return warnings
