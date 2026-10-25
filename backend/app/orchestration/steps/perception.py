"""Pipeline perception steps — split from document_pipeline_orchestrator.py (runs/split batch 3).

Step bodies moved verbatim (tier A); only this import header is new (tier B).
The orchestrator class import is TYPE_CHECKING-only (annotations stay strings).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Dict, List
from loguru import logger
from app.core.config import settings
if TYPE_CHECKING:
    from app.orchestration.document_pipeline_orchestrator import DocumentPipelineOrchestrator
PipelineContext = Dict[str, Any]


def _collect_layout_blocks(
    layout_result: Dict[str, Any],
    *,
    accepted_types: set,
) -> List[Dict[str, Any]]:
    """Collect normalized [x1,y1,x2,y2] boxes from layout elements for given types."""
    out: List[Dict[str, Any]] = []
    if not isinstance(layout_result, dict):
        return out

    elements = layout_result.get("elements", [])
    if not isinstance(elements, list):
        return out

    for el in elements:
        if not isinstance(el, dict):
            continue
        t = str(el.get("type", "")).strip().lower()
        if t not in accepted_types:
            continue

        bbox = el.get("bbox", {})
        if not isinstance(bbox, dict):
            continue
        try:
            x1 = float(bbox.get("x", 0.0))
            y1 = float(bbox.get("y", 0.0))
            w = float(bbox.get("width", 0.0))
            h = float(bbox.get("height", 0.0))
            if w <= 0 or h <= 0:
                continue
            out.append(
                {
                    "x1": x1,
                    "y1": y1,
                    "x2": x1 + w,
                    "y2": y1 + h,
                    "source_id": el.get("id", ""),
                    "source_type": t,
                }
            )
        except Exception:
            continue
    return out


async def layout_step(ctx: PipelineContext) -> None:
    options = ctx["options"]
    if not options.get("enable_layout", True):
        return

    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    task_id = ctx["task_id"]

    orchestrator.ensure_not_cancelled(ctx)

    engine_name = options.get("layout_engine") or "ppstructure"
    await orchestrator.update_progress(ctx, 25, f"Trying layout analysis with {engine_name.title()}...")

    layout_result = await orchestrator.call_maybe_async(
        orchestrator.services["layout_service"].analyze,
        ctx["file_path"],
        engine=options.get("layout_engine"),
        fallback=True,
    )
    orchestrator.ensure_not_cancelled(ctx)

    elements = layout_result.get("elements", [])

    if ctx.get("debug_overlay_enabled") and orchestrator.save_debug_overlay:
        artifact = orchestrator.save_debug_overlay(
            file_path=ctx["file_path"],
            task_id=task_id,
            stage="layout_raw",
            elements=elements,
            page_num=1,
        )
        if artifact:
            ctx["result"]["document_info"].setdefault("debug_artifacts", []).append(artifact)

    ctx["result"]["layout"] = layout_result
    ctx["result"]["layout_engine_used"] = layout_result.get("engine_used")

    # When PaddleOCR applied unwarping, bboxes live in output_img space.
    # Update page_image_meta dimensions and store the preprocessed image path
    # so the /page-image endpoint serves the correct image.
    prep_path = layout_result.get("preprocessed_image_path")
    if prep_path:
        ctx["result"]["document_info"]["page_image_meta"]["width_px"] = int(
            layout_result.get("preprocessed_image_width") or 0
        )
        ctx["result"]["document_info"]["page_image_meta"]["height_px"] = int(
            layout_result.get("preprocessed_image_height") or 0
        )
        ctx["task"]["preprocessed_image_path"] = prep_path
        logger.info(f"Task {task_id}: preprocessed image stored for bbox alignment: {prep_path}")

    await orchestrator.update_progress(ctx, 45, "Layout analysis completed")


async def figure_step(ctx: PipelineContext) -> None:
    """Crop figure regions and run split-figure integrity checks (GLM trial P0-2).

    Runs right after layout_step so element bboxes (and the preprocessed
    coordinate space) are fresh. Best-effort: failures are recorded in
    ctx["result"]["figures"]["errors"] and never fail the task.
    """
    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    task_id = ctx["task_id"]

    options = ctx.get("options", {}) if isinstance(ctx.get("options"), dict) else {}
    if not options.get("enable_figure_export", True):
        return

    layout_result = ctx["result"].get("layout")
    if not isinstance(layout_result, dict) or not layout_result.get("elements"):
        return

    orchestrator.ensure_not_cancelled(ctx)
    await orchestrator.update_progress(ctx, 47, "Cropping figure regions...")

    try:
        from app.services.figure_service import FigureService

        figure_service = FigureService()
        output_dir = os.path.join(settings.OUTPUT_DIR, task_id, "figures")
        figures_result = figure_service.crop_figures(
            file_path=ctx["file_path"],
            layout_result=layout_result,
            output_dir=output_dir,
            task_id=task_id,
        )
        # Drop absolute paths from the API-facing dict (keep crops on disk).
        public = {
            "figure_count": figures_result.get("figure_count", 0),
            "cropped_count": figures_result.get("cropped_count", 0),
            "merged_count": figures_result.get("merged_count", 0),
            "warnings": figures_result.get("warnings", []),
            "errors": figures_result.get("errors", []),
            "items": [
                {
                    "id": item.get("id"),
                    "page": item.get("page"),
                    "type": item.get("type"),
                    "confidence": item.get("confidence"),
                    "bbox": item.get("bbox"),
                    "width_px": item.get("width_px"),
                    "height_px": item.get("height_px"),
                    "caption": item.get("caption") or "",
                    "caption_id": item.get("caption_id") or "",
                    "crop_url": item.get("crop_url"),
                    # Merged-crop fields (absent for normal figure crops).
                    "is_merged": item.get("is_merged", False),
                    "merged_from": item.get("merged_from") or [],
                    "split_kind": item.get("split_kind") or "",
                }
                for item in figures_result.get("figures", [])
            ],
        }
        ctx["result"]["figures"] = public
        if public["figure_count"] or public["warnings"]:
            logger.info(
                f"Task {task_id}: figures detected={public['figure_count']} "
                f"cropped={public['cropped_count']} split_warnings={len(public['warnings'])}"
            )
    except Exception as exc:  # noqa: BLE001 — figure export must not break analysis
        logger.warning(f"Task {task_id}: figure_step failed (non-fatal): {exc}")
        ctx["result"]["figures"] = {"errors": [{"id": None, "reason": str(exc)}]}
