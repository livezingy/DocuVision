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

            os.makedirs(output_dir, exist_ok=True)

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
                    source = pages.get(page_no) or pages.get(1)
                    if source is None:
                        raise RuntimeError(f"no raster source for page {page_no}")
                    img, width, height = source
                    box = _clamp_box(_bbox_tuple(elem), width, height)
                    if box[2] - box[0] < MIN_CROP_PX or box[3] - box[1] < MIN_CROP_PX:
                        result["errors"].append(
                            {"id": elem.get("id"), "reason": "degenerate_bbox_after_clamp"}
                        )
                        continue
                    crop = img.crop((int(box[0]), int(box[1]), int(box[2]), int(box[3])))
                    fig_id = str(elem.get("id") or f"p{page_no}_fig")
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
            result["warnings"] = detect_split_warnings(figures, page_height)
        except Exception as exc:  # noqa: BLE001 — service must never fail the pipeline
            logger.warning("figure_service: crop_figures failed: {}", exc)
            result["errors"].append({"id": None, "reason": str(exc)})
        return result

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
