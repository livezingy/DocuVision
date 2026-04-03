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


async def ocr_step(ctx: PipelineContext) -> None:
    options = ctx["options"]
    if not options.get("enable_ocr", False):
        return

    task_id = ctx["task_id"]
    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]

    engine_name = options.get("ocr_engine") or "paddleocr"
    await orchestrator.update_progress(ctx, 5, f"Trying OCR with {engine_name.title()}...")

    ocr_result = await orchestrator.call_maybe_async(
        orchestrator.services["ocr_service"].recognize,
        ctx["file_path"],
        language=options.get("language", "en"),
        engine=options.get("ocr_engine"),
        fallback=True,
    )

    ctx["result"]["text_blocks"] = ocr_result.get("text_blocks", [])
    ctx["result"]["document_info"]["pages"] = ocr_result.get("page_count", 0)
    ctx["result"]["ocr_engine_used"] = ocr_result.get("engine_used")
    ctx["result"]["full_text"] = ocr_result.get("full_text", "")

    try:
        ctx["result"]["semantic_text_blocks"] = orchestrator.services["layout_service"].build_semantic_text_blocks(
            ctx["result"].get("text_blocks", []),
            layout_elements=[],
        )
    except Exception as exc:
        logger.warning(f"Task {task_id}: failed to build OCR semantic blocks: {exc}")
        ctx["result"]["semantic_text_blocks"] = []

    await orchestrator.update_progress(ctx, 25, "OCR completed")


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

    if ctx["result"].get("text_blocks") and orchestrator.services["layout_service"].is_ready():
        try:
            engine = orchestrator.services["layout_service"].get_engine(layout_result.get("engine_used"))
            if hasattr(engine, "_supplement_text_from_ocr"):
                elements = engine._supplement_text_from_ocr(elements, ctx["result"].get("text_blocks", []))
                layout_result["elements"] = elements
        except Exception as exc:
            logger.warning(f"Task {task_id}: failed to supplement text from OCR: {exc}")

    try:
        ctx["result"]["semantic_text_blocks"] = orchestrator.services["layout_service"].build_semantic_text_blocks(
            ctx["result"].get("text_blocks", []),
            layout_elements=elements,
        )
    except Exception as exc:
        logger.warning(f"Task {task_id}: failed to build layout semantic blocks: {exc}")

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
        ocr_text_blocks=ctx["result"].get("text_blocks", []),
    )
    orchestrator.ensure_not_cancelled(ctx)

    ctx["result"]["tables"] = table_result if isinstance(table_result, list) else []
    await orchestrator.update_progress(ctx, 65, f"Table extraction completed | Tables: {len(ctx['result']['tables'])}")


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

async def phase1_preprocessing_step(ctx: PipelineContext) -> None:
    """Extract and store preprocessing metadata for Phase 1 Envelope."""
    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    task_id = ctx["task_id"]

    layout_result = ctx["result"].get("layout", {})
    if not layout_result:
        return

    # Metadata will be built when building envelope; store references for now
    ctx["phase1_layout_result"] = layout_result


async def phase1_envelope_step(ctx: PipelineContext) -> None:
    """Build Phase 1 Envelope (preprocessing, raw, fused, view, quality layers)."""
    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    task_id = ctx["task_id"]

    await orchestrator.update_progress(ctx, 75, "Building Phase 1 Envelope...")

    try:
        from app.orchestration.envelope_builder import EnvelopeBuilder
        from app.core.config import settings

        builder = EnvelopeBuilder(settings)

        layout_result = ctx.get("phase1_layout_result") or ctx["result"].get("layout", {})
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

        # 3. Per-block OCR: crop each text-type block from the preprocessed image
        #    and run PaddleOCR on the crop.  Results keyed by element id.
        import cv2 as _cv2

        preprocessed_image_path = ctx["task"].get("preprocessed_image_path") or file_path
        _prep_img = None
        try:
            _prep_img = _cv2.imread(preprocessed_image_path)
            if _prep_img is None and preprocessed_image_path != file_path:
                _prep_img = _cv2.imread(file_path)
        except Exception as _exc_img:
            logger.warning(f"Task {task_id}: failed to load image for per-block OCR: {_exc_img}")

        per_block_ocr: Dict[str, Any] = {}
        if _prep_img is not None:
            ocr_svc = orchestrator.services.get("ocr_service")
            _elements = layout_result.get("elements", [])
            logger.info(f"Task {task_id}: per-block OCR on {len(_elements)} elements")
            for _elem in _elements:
                if not isinstance(_elem, dict):
                    continue
                if _elem.get("type", "").lower() not in builder._OCR_TEXT_LABELS:
                    continue
                _bbox = _elem.get("bbox") or {}
                _x0 = int(float(_bbox.get("x", 0)))
                _y0 = int(float(_bbox.get("y", 0)))
                _x1 = _x0 + int(float(_bbox.get("width", 0)))
                _y1 = _y0 + int(float(_bbox.get("height", 0)))
                if _x1 <= _x0 or _y1 <= _y0:
                    continue
                _h_img, _w_img = _prep_img.shape[:2]
                if _elem.get("type", "").lower() == "text":
                    _pad_x = max(2, int((_x1 - _x0) * 0.06))
                    _pad_y = max(2, int((_y1 - _y0) * 0.06))
                    _x0 -= _pad_x
                    _x1 += _pad_x
                    _y0 -= _pad_y
                    _y1 += _pad_y
                _x0 = max(0, _x0); _y0 = max(0, _y0)
                _x1 = min(_w_img, _x1); _y1 = min(_h_img, _y1)
                if _x1 <= _x0 or _y1 <= _y0:
                    continue
                _crop = _prep_img[_y0:_y1, _x0:_x1]
                if _crop.size == 0:
                    continue
                try:
                    _lines = ocr_svc.recognize_block_array(_crop) if ocr_svc else []
                except Exception as _exc_ocr:
                    logger.debug(f"Task {task_id}: per-block OCR failed for {_elem.get('id')}: {_exc_ocr}")
                    _lines = []
                per_block_ocr[str(_elem.get("id", ""))] = {
                    "lines": _lines,
                    "crop_offset": [_x0, _y0],
                }
            logger.info(f"Task {task_id}: per-block OCR completed, {len(per_block_ocr)} blocks processed")

        # Keep raw layer aligned with design artifacts
        raw["paddleocr_blocks"] = per_block_ocr

        # 4. Build fused layer (per-block OCR text fusion)
        fused = builder.build_fused_layer(
            layout_result=layout_result,
            per_block_ocr=per_block_ocr,
            ocr_confidence_threshold=settings.OCR_MIN_CONFIDENCE,
            suspicious_length_ratio=settings.OCR_SUSPICIOUS_LENGTH_RATIO,
        )
        ctx["phase1_fused"] = fused

        # 5. Build view layer (coordinate transformation + reading order)
        view = builder.build_view_layer(
            fused_layer=fused,
            preprocessing_metadata=preprocessing,
            original_image_path=file_path,
            preprocessed_image_path=preprocessed_image_path,
        )
        ctx["phase1_view"] = view

        # 6. Build quality layer
        quality = builder.build_quality_layer(
            fused_layer=fused,
            processing_time_ms=processing_time_ms,
            engines_used=["doc_preprocessor", "pp_structure_v3", "paddleocr"],
        )
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
            ocr_step,
            layout_step,
            table_step,
            phase1_preprocessing_step,  # Capture preprocessing metadata reference
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
