"""Document processing pipeline orchestrator.

This module owns pipeline sequencing and task state progression.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

from loguru import logger


PipelineContext = Dict[str, Any]


async def _run_progressed_step(
    ctx: PipelineContext,
    *,
    progress: int,
    message: str,
    func: Callable[[PipelineContext], Awaitable[None]],
) -> None:
    await ctx["orchestrator"].update_progress(ctx, progress, message)
    await func(ctx)


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


async def table_step(ctx: PipelineContext) -> None:
    options = ctx["options"]
    if not options.get("enable_table", True):
        return

    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)

    engine_name = options.get("table_engine") or "ppstructure"
    await orchestrator.update_progress(ctx, 45, f"Trying table extraction with {engine_name.title()}...")

    layout_elements = ctx["result"].get("layout", {}).get("elements", []) if ctx["result"].get("layout") else None
    table_result = await orchestrator.call_maybe_async(
        orchestrator.services["table_service"].extract,
        ctx["file_path"],
        engine=options.get("table_engine"),
        fallback=True,
        layout_elements=layout_elements,
    )
    orchestrator.ensure_not_cancelled(ctx)

    ctx["result"]["tables"] = table_result if isinstance(table_result, list) else []
    await orchestrator.update_progress(ctx, 65, f"Table extraction completed | Tables: {len(ctx['result']['tables'])}")


async def formula_step(ctx: PipelineContext) -> None:
    options = ctx["options"]
    if not options.get("enable_formula", False):
        return

    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)
    await orchestrator.update_progress(ctx, 70, "Running formula recognition...")

    formula_service = orchestrator.services.get("formula_service")
    if formula_service is None:
        logger.warning("Formula step enabled but formula_service is not available; skipping")
        return

    formula_result = await orchestrator.call_maybe_async(
        formula_service.recognize,
        ctx["file_path"],
        disable_layout=bool(options.get("formula_disable_layout", False)),
        disable_preprocess=bool(options.get("formula_disable_preprocess", False)),
        two_stage_threshold_retry=bool(options.get("formula_two_stage_threshold_retry", True)),
        primary_layout_threshold=float(options.get("formula_primary_layout_threshold", 0.5)),
        fallback_layout_threshold=float(options.get("formula_fallback_layout_threshold", 0.2)),
        layout_threshold=(
            float(options["formula_layout_threshold"])
            if options.get("formula_layout_threshold") is not None
            else None
        ),
        pipeline_formula_batch_size=int(options.get("pipeline_formula_batch_size", 1)),
    )

    if not isinstance(formula_result, dict) or not formula_result.get("ok", False):
        logger.warning(f"Formula recognition skipped or failed: {formula_result}")
        return

    ctx["result"]["formula_unwrapped_results"] = formula_result.get("unwrapped_results", [])
    ctx["result"]["formula_stats"] = formula_result.get("stats", {})
    ctx["result"]["formula_stage"] = formula_result.get("stage")

    formula_count = int(formula_result.get("stats", {}).get("formula_count", 0))
    await orchestrator.update_progress(ctx, 74, f"Formula recognition completed | Formulas: {formula_count}")


async def finalize_step(ctx: PipelineContext) -> None:
    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)

    task = ctx["task"]
    task["progress"] = 100
    # Keep "completed" for frontend compatibility; Phase 1 job routes accept both "succeeded" and "completed"
    task["status"] = "completed"
    task["message"] = "Processing completed"
    task["completed_at"] = datetime.now()
    task["result"] = ctx["result"]

    await orchestrator.send_event(ctx["task_id"], "completed", "Processing completed", 100)


# ============================================
# Phase 1 Pipeline Steps - Envelope Building
# ============================================

async def phase1_envelope_step(ctx: PipelineContext) -> None:
    """Build Phase 1 Envelope (preprocessing, raw, fused, view, quality layers)."""
    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    task_id = ctx["task_id"]

    await orchestrator.update_progress(ctx, 75, "Building Phase 1 Envelope...")

    try:
        from app.orchestration.envelope_builder import EnvelopeBuilder
        from app.core.config import settings

        builder = EnvelopeBuilder(settings)

        layout_result = ctx["result"].get("layout", {})
        file_path = ctx["file_path"]

        start_time = ctx.get("start_time", datetime.now())
        processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        # 1. Build preprocessing metadata
        preprocessing = builder.build_preprocessing_metadata(
            layout_result=layout_result,
            use_doc_unwarping=settings.USE_DOC_UNWARPING,
        )
        ctx["phase1_preprocessing"] = preprocessing

        # 2. Build raw layer
        raw = builder.build_raw_layer(layout_result=layout_result)
        ctx["phase1_raw"] = raw

        preprocessed_image_path = ctx["task"].get("preprocessed_image_path") or file_path

        # 3. Build fused layer (PPStructureV3 content used directly, no per-block OCR)
        fused = builder.build_fused_layer(layout_result=layout_result)
        ctx["phase1_fused"] = fused

        # 3.1 Merge formula recognition output into fused/view/quality.
        formula_unwrapped_results = ctx["result"].get("formula_unwrapped_results", [])
        formula_adapted = None
        if formula_unwrapped_results:
            from app.services.formula_service import adapt_formula_results_for_backend

            first_page_blocks = fused.get("pages", [{}])[0].get("blocks", []) if fused.get("pages") else []
            max_reading_order = len(first_page_blocks)

            formula_adapted = adapt_formula_results_for_backend(
                formula_unwrapped_results,
                page_number=1,
                reading_order_start=max_reading_order + 1,
            )

            if fused.get("pages"):
                page0 = fused["pages"][0]
                existing_blocks = page0.get("blocks", [])
                filtered_blocks = [
                    b for b in existing_blocks
                    if not (
                        str(b.get("type", "")).lower() in {"formula", "inline_formula"}
                        and str(b.get("processing_status", "")).lower() == "skip_formula"
                    )
                ]
                filtered_blocks.extend(formula_adapted.get("fused_formula_blocks", []))
                page0["blocks"] = filtered_blocks

        # 4. Build view layer (coordinate transformation + reading order)
        view = builder.build_view_layer(
            fused_layer=fused,
            preprocessing_metadata=preprocessing,
            original_image_path=file_path,
            preprocessed_image_path=preprocessed_image_path,
        )

        if formula_adapted is not None:
            view["formulas"] = formula_adapted.get("view_formulas", [])

        ctx["phase1_view"] = view

        # 5. Build quality layer
        quality = builder.build_quality_layer(
            fused_layer=fused,
            processing_time_ms=processing_time_ms,
            engines_used=["doc_preprocessor", "pp_structure_v3"],
        )
        if formula_adapted is not None:
            quality.update(formula_adapted.get("quality_patch", {}))
        ctx["phase1_quality"] = quality

        # 6. Save debug artifacts if enabled
        if settings.DEBUG_MODE:
            builder.save_debug_artifacts(
                job_id=task_id,
                preprocessing=preprocessing,
                raw=raw,
                fused=fused,
                quality=quality,
                original_image_path=file_path,
                preprocessed_image_path=preprocessed_image_path,
            )

        # 7. Construct Envelope and attach to task
        # Note: We store as dict; main.py will convert to JobEnvelope when returning
        envelope_dict = {
            "job_id": task_id,
            "status": "succeeded",
            "version": "1.0",
            "preprocessing": preprocessing,
            "raw": raw,
            "fused": fused,
            "view": view,
            "quality": quality,
        }
        ctx["task"]["envelope"] = envelope_dict

        await orchestrator.update_progress(ctx, 90, "Phase 1 Envelope built")

    except Exception as e:
        logger.error(f"Task {task_id}: Phase 1 envelope building failed: {e}")
        logger.exception(e)
        raise


class DocumentPipelineOrchestrator:
    """Orchestrates document processing and task-state transitions."""

    def __init__(
        self,
        *,
        services: Dict[str, Any],
        send_event: Callable[[str, str, str, Optional[float]], Awaitable[None]],
        is_cancelled: Callable[[str], bool],
        call_maybe_async: Callable[..., Awaitable[Any]],
        build_page_image_meta: Callable[..., Dict[str, Any]],
        save_debug_overlay: Optional[Callable[..., Optional[Dict[str, Any]]]] = None,
    ) -> None:
        self.services = services
        self.send_event = send_event
        self.is_cancelled = is_cancelled
        self.call_maybe_async = call_maybe_async
        self.build_page_image_meta = build_page_image_meta
        self.save_debug_overlay = save_debug_overlay

    def ensure_not_cancelled(self, ctx: PipelineContext) -> None:
        task_id = ctx["task_id"]
        if self.is_cancelled(task_id):
            ctx["task"]["status"] = "cancelled"
            ctx["task"]["message"] = "Task cancelled"
            raise asyncio.CancelledError("Task cancelled")

    async def update_progress(self, ctx: PipelineContext, progress: int, message: str) -> None:
        task = ctx["task"]
        task["progress"] = progress
        task["message"] = message
        await self.send_event(ctx["task_id"], "log", message, progress)

    async def run(self, task_id: str, task: Dict[str, Any]) -> None:
        self.ensure_not_cancelled({"task_id": task_id, "task": task})

        task["status"] = "processing"
        task["message"] = "Processing document..."
        await self.send_event(task_id, "status", "Processing document...", 0)

        result: Dict[str, Any] = {
            "document_info": {
                "file_name": task["file_name"],
                "pages": 0,
                "processed_at": datetime.now().isoformat(),
                "page_image_meta": self.build_page_image_meta(task["file_path"], task_id=task_id, page_num=1),
                "debug_artifacts": [],
            }
        }

        ctx: PipelineContext = {
            "task_id": task_id,
            "task": task,
            "file_path": task["file_path"],
            "options": task.get("options", {}),
            "result": result,
            "orchestrator": self,
            "debug_overlay_enabled": str(os.environ.get("DOCUVISION_DEBUG_OVERLAY", "1")).strip().lower() in {"1", "true", "yes", "y", "on"},
            "start_time": datetime.now(),
        }

        steps = [
            layout_step,
            table_step,
            formula_step,
            phase1_envelope_step,  # Build Phase 1 Envelope (preprocessing, raw, fused, view, quality)
            finalize_step,
        ]

        try:
            for step in steps:
                await step(ctx)
        except asyncio.CancelledError:
            await self.send_event(task_id, "cancelled", "Task cancelled")
            return
        except Exception as exc:
            logger.error(f"Task failed: {task_id} | File: {task.get('file_name', 'unknown')} | Error: {exc}")
            logger.exception(exc)
            task["status"] = "failed"
            task["message"] = f"Processing failed: {exc}"
            return
