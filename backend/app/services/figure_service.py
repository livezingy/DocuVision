"""Figure region cropping and integrity validation (facade).

Keeps ``FigureService`` (crop/IO side: raster rendering, per-figure crop
isolation, merged re-crops) and re-exports the split-detect heuristics now
living in ``figure_split_detect.py`` (S1 batch 9 split of the former
monolith). Best-effort contract unchanged: any per-figure error is recorded
in ``errors`` and never propagates into the pipeline.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from app.services.bbox_geometry import (  # noqa: F401 (re-export; moved verbatim, batch P-038 A+)
    _bbox_tuple,
    _clamp_box,
    _containment_ratio,
    _h_overlap_ratio,
    _merged_box,
    _v_gap,
    _v_overlap_ratio,
)
from app.services.figure_split_detect import (  # noqa: F401 (re-export; test import surface)
    CAPTION_LABELS,
    COMPLETE_FIG_H_RATIO,
    FIGURE_LABELS,
    MIN_CROP_PX,
    TABLE_CAPTION_LABELS,
    _bind_captions,
    _both_complete_looking,
    _caption_elements,
    _detect_bbox_space_mismatch,
    _distinct_bound_captions,
    _figure_elements,
    detect_split_warnings,
)


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
