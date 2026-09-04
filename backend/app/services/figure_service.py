"""Figure region cropping and integrity validation (GLM trial P0-2).

Why this module exists
----------------------
Layout analysis (PP-StructureV3) already detects figure/chart regions, but
the Pro pipeline never exported the crops and had no signal for a figure
that the detector *split in half* (a common failure mode when layout NMS
splits one large diagram into stacked regions). This service closes both
gaps at the layout layer without touching any engine contract.

Coordinate spaces (must stay aligned with layout_service)
---------------------------------------------------------
- PDF: elements are detected on a per-page 2x raster produced with
  ``fitz.Matrix(2, 2)`` inside ``_analyze_pdf`` — we re-render each page
  with the SAME matrix before cropping.
- Images: elements are in the PREPROCESSED space (rotation/unwarp applied
  by doc_preprocessor); we crop from ``preprocessed_image_path`` when the
  layout result carries one, otherwise from the original file.

Failure policy
--------------
This service is best-effort: any per-figure error is recorded in
``errors`` and never propagates into the pipeline. A figure crop failure
must not fail a document analysis job.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

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


# ---------------------------------------------------------------------------
# Cropping
# ---------------------------------------------------------------------------

class FigureService:
    """Crop figure regions from the analyzed raster and validate integrity."""

    def crop_figures(
        self,
        *,
        file_path: str,
        layout_result: Dict[str, Any],
        output_dir: str,
        api_prefix: str = "/api/v1/tasks",
        task_id: str = "",
    ) -> Dict[str, Any]:
        """Export figure crops for one task.

        Returns a result dict (never raises):
        {
          "figures": [...], "warnings": [...], "errors": [...],
          "figure_count": int, "cropped_count": int
        }
        """
        result: Dict[str, Any] = {
            "figures": [],
            "warnings": [],
            "errors": [],
            "figure_count": 0,
            "cropped_count": 0,
            "source": {"mode": "", "preprocessed": False},
        }
        try:
            elements = layout_result.get("elements") or []
            figures = _figure_elements(elements)
            result["figure_count"] = len(figures)
            if not figures:
                return result

            # F3: bind caption elements to figures before cropping so the
            # result carries caption text alongside each figure crop.
            _bind_captions(figures, elements)

            os.makedirs(output_dir, exist_ok=True)

            # Track figure ids seen so far to defend against id collisions
            # (same id on multiple pages). The layout worker now stamps ids
            # with the real page number, but this guard prevents silent
            # crop-file overwrites if a regression ever reintroduces
            # duplicate ids (e.g. a legacy worker using the 2-tuple wire
            # format with page_num dropped).
            seen_crop_ids: set = set()

            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".pdf":
                pages = self._render_pdf_pages(file_path, figures)
                result["source"] = {"mode": "pdf", "preprocessed": False}
            else:
                prep_path = layout_result.get("preprocessed_image_path")
                used_prep = bool(prep_path and os.path.exists(prep_path))
                pages = self._load_image_source(file_path, layout_result)
                result["source"] = {"mode": "image", "preprocessed": used_prep}

            for elem in figures:
                try:
                    page_no = int(elem.get("page", 1) or 1)
                    # No silent fallback to page 1: a missing/wrong page_no
                    # must surface as an error (per-figure) instead of
                    # cropping all such figures from page 1's raster, which
                    # previously produced many identical crops silently.
                    source = pages.get(page_no)
                    if source is None:
                        raise RuntimeError(
                            f"no raster source for page {page_no} "
                            f"(rendered pages: {sorted(pages.keys())})"
                        )
                    img, width, height = source
                    box = _clamp_box(_bbox_tuple(elem), width, height)
                    if box[2] - box[0] < MIN_CROP_PX or box[3] - box[1] < MIN_CROP_PX:
                        result["errors"].append(
                            {"id": elem.get("id"), "reason": "degenerate_bbox_after_clamp"}
                        )
                        continue
                    crop = img.crop((int(box[0]), int(box[1]), int(box[2]), int(box[3])))
                    fig_id = str(elem.get("id") or f"p{page_no}_fig")
                    # Defense against id collision: if the same fig_id was
                    # already cropped (e.g. duplicate ids across pages from a
                    # legacy worker), suffix with the page number so the new
                    # crop does not overwrite the previous file. The
                    # collision is logged so a regression is visible.
                    if fig_id in seen_crop_ids:
                        logger.warning(
                            "figure_service: duplicate figure id {} on page {} — "
                            "suffixing crop filename to avoid overwrite",
                            fig_id, page_no,
                        )
                        fig_id = f"{fig_id}_p{page_no}"
                    seen_crop_ids.add(fig_id)
                    filename = f"{fig_id}.png"
                    crop_path = os.path.join(output_dir, filename)
                    crop.save(crop_path, format="PNG")
                    result["figures"].append(
                        {
                            "id": fig_id,
                            "page": page_no,
                            "type": elem.get("type"),
                            "confidence": elem.get("confidence", 0.0),
                            "bbox": elem.get("bbox"),
                            "width_px": crop.width,
                            "height_px": crop.height,
                            "crop_path": crop_path,
                            # F3: caption bound by _bind_captions (may be absent).
                            "caption": elem.get("caption") or "",
                            "caption_id": elem.get("caption_id") or "",
                            # Served by GET /api/v1/tasks/{task_id}/figures/{figure_id}
                            # (route accepts the bare element id; .png is
                            # appended server-side and dots are rejected by
                            # the traversal guard).
                            "crop_url": (
                                f"{api_prefix}/{task_id}/figures/{fig_id}" if task_id else None
                            ),
                        }
                    )
                except Exception as exc:  # noqa: BLE001 — per-figure isolation
                    logger.warning("figure_service: crop failed for {}: {}", elem.get("id"), exc)
                    result["errors"].append({"id": elem.get("id"), "reason": str(exc)})

            result["cropped_count"] = len(result["figures"])

            page_height = 0
            for source in pages.values():
                page_height = max(page_height, source[2])
            split_warnings = detect_split_warnings(figures, page_height)
            # Coordinate-space self-check: flag any figure bbox that exceeds
            # its page raster dimensions, which signals the bbox lives in a
            # different space (e.g. rotated preprocessed space) than the
            # crop raster -- the leading cause of identical wrong crops.
            bbox_warnings = _detect_bbox_space_mismatch(figures, pages)
            result["warnings"] = split_warnings + bbox_warnings
            if bbox_warnings:
                logger.warning(
                    "figure_service: {} bbox/raster space mismatch warning(s) "
                    "(first: {})",
                    len(bbox_warnings),
                    bbox_warnings[0],
                )

            # Consume split warnings: re-crop a merged image for vertical /
            # horizontal splits so the caller gets one whole diagram instead
            # of two halves. nested_regions is a caption-inside-figure case,
            # NOT a split — skipped to avoid merging a caption into the crop.
            # The original half-crops are kept as fallback so a false-positive
            # merge (two independent figures stacked) can still be recovered
            # downstream by inspecting merged_from.
            self._crop_merged_splits(
                result=result,
                warnings=result["warnings"],
                pages=pages,
                output_dir=output_dir,
                api_prefix=api_prefix,
                task_id=task_id,
            )
            # cropped_count reflects individual figure crops only; merged
            # crops are reported separately via merged_count.
            result["merged_count"] = sum(
                1 for f in result["figures"] if f.get("is_merged")
            )
        except Exception as exc:  # noqa: BLE001 — service must never fail the pipeline
            logger.warning("figure_service: crop_figures failed: {}", exc)
            result["errors"].append({"id": None, "reason": str(exc)})
        return result

    def _crop_merged_splits(
        self,
        *,
        result: Dict[str, Any],
        warnings: List[Dict[str, Any]],
        pages: Dict[int, Tuple[Any, int, int]],
        output_dir: str,
        api_prefix: str,
        task_id: str,
    ) -> None:
        """Re-crop a single merged image for each split-figure warning.

        Only ``possible_vertical_split`` and ``possible_horizontal_split``
        are consumed; ``nested_regions`` is a caption/inner box inside a
        figure and must NOT be merged. The merged crop is appended to
        ``result["figures"]`` with ``is_merged=True`` and ``merged_from``
        listing the original half-figure ids, so downstream can prefer the
        merged crop while still recovering the halves via ``merged_from``.

        Best-effort: per-merge errors are recorded in ``result["errors"]``
        and never propagate.
        """
        split_kinds = {"possible_vertical_split", "possible_horizontal_split"}
        for w in warnings or []:
            if w.get("kind") not in split_kinds:
                continue
            page_no = int(w.get("page", 1) or 1)
            source = pages.get(page_no) or pages.get(1)
            if source is None:
                result["errors"].append(
                    {"id": None, "reason": f"merged crop skipped: no raster for page {page_no}"}
                )
                continue
            img, width, height = source
            mb = w.get("merged_bbox") or {}
            box = _clamp_box(
                (float(mb.get("x", 0)), float(mb.get("y", 0)),
                 float(mb.get("x", 0)) + float(mb.get("width", 0)),
                 float(mb.get("y", 0)) + float(mb.get("height", 0))),
                width,
                height,
            )
            if box[2] - box[0] < MIN_CROP_PX or box[3] - box[1] < MIN_CROP_PX:
                result["errors"].append(
                    {"id": None, "reason": "merged crop skipped: degenerate merged_bbox"}
                )
                continue
            ids = w.get("ids") or []
            merged_id = "merged_" + "_".join(str(i) for i in ids) if ids else f"merged_p{page_no}"
            try:
                crop = img.crop((int(box[0]), int(box[1]), int(box[2]), int(box[3])))
                crop_path = os.path.join(output_dir, f"{merged_id}.png")
                crop.save(crop_path, format="PNG")
                result["figures"].append(
                    {
                        "id": merged_id,
                        "page": page_no,
                        "type": "merged_figure",
                        "confidence": 0.0,
                        "bbox": {
                            "x": float(mb.get("x", 0)),
                            "y": float(mb.get("y", 0)),
                            "width": float(mb.get("width", 0)),
                            "height": float(mb.get("height", 0)),
                        },
                        "width_px": crop.width,
                        "height_px": crop.height,
                        "crop_path": crop_path,
                        "caption": "",
                        "caption_id": "",
                        "crop_url": (
                            f"{api_prefix}/{task_id}/figures/{merged_id}" if task_id else None
                        ),
                        "is_merged": True,
                        "merged_from": ids,
                        "split_kind": w.get("kind"),
                    }
                )
            except Exception as exc:  # noqa: BLE001 — per-merge isolation
                logger.warning("figure_service: merged crop failed for {}: {}", ids, exc)
                result["errors"].append(
                    {"id": None, "reason": f"merged crop failed for {ids}: {exc}"}
                )

    def _render_pdf_pages(
        self, file_path: str, figures: List[Dict[str, Any]]
    ) -> Dict[int, Tuple[Any, int, int]]:
        """Render the referenced PDF pages with the SAME 2x matrix used by
        layout_service._analyze_pdf, so element bboxes align with pixels."""
        import fitz
        from PIL import Image

        wanted = sorted({int(f.get("page", 1) or 1) for f in figures})
        pages: Dict[int, Tuple[Any, int, int]] = {}
        doc = fitz.open(file_path)
        try:
            page_count = len(doc)
            for page_no in wanted:
                if page_no < 1 or page_no > page_count:
                    continue
                pix = doc[page_no - 1].get_pixmap(matrix=fitz.Matrix(2, 2))
                if pix.alpha:
                    img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
                    img = img.convert("RGB")
                else:
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                pages[page_no] = (img, pix.width, pix.height)
        finally:
            doc.close()
        return pages

    def _load_image_source(
        self, file_path: str, layout_result: Dict[str, Any]
    ) -> Dict[int, Tuple[Any, int, int]]:
        """Image files: crop in the preprocessed space when available."""
        from PIL import Image

        source_path: Optional[str] = layout_result.get("preprocessed_image_path")
        if not source_path or not os.path.exists(source_path):
            source_path = file_path
        img = Image.open(source_path)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        return {1: (img, img.width, img.height)}
