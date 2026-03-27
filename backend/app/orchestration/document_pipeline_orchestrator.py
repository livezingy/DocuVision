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
    if not options.get("enable_ocr", True):
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

    try:
        from app.services.canonical_converter import CanonicalConverter

        converter = CanonicalConverter()
        source_type = "pdf" if str(ctx["file_path"]).lower().endswith(".pdf") else "image"
        canonical_doc = converter.convert(
            task_id=task_id,
            source_type=source_type,
            layout_result=layout_result,
            ocr_result=ctx["result"].get("ocr"),
            doc_type_hint=options.get("doc_type", "unknown"),
            file_path=ctx["file_path"],
        )
        ctx["result"]["canonical"] = canonical_doc.to_dict(include_raw_payload=True)
        ctx["result"]["canonical_summary"] = canonical_doc.summary()
    except Exception as exc:
        logger.warning(f"Task {task_id}: canonical conversion failed (non-fatal): {exc}")

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


async def barcode_step(ctx: PipelineContext) -> None:
    options = ctx["options"]
    if not options.get("enable_barcode", False):
        return

    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)

    await orchestrator.update_progress(ctx, 65, "Barcode recognition...")
    try:
        from app.modules.barcode_recognition import BarcodeRecognitionModule

        barcode_module = BarcodeRecognitionModule(config={"engine": options.get("barcode_engine", "pyzbar")})
        barcode_module.initialize()
        if barcode_module.is_ready():
            barcode_result = await orchestrator.call_maybe_async(
                barcode_module.process,
                ctx["file_path"],
                engine=options.get("barcode_engine"),
                fallback=True,
            )
            ctx["result"]["barcodes"] = barcode_result.get("barcodes", [])
            ctx["result"]["barcode_count"] = barcode_result.get("count", 0)
        else:
            ctx["result"]["barcodes"] = []
            ctx["result"]["barcode_count"] = 0
    except Exception as exc:
        logger.warning(f"Task {ctx['task_id']}: barcode recognition failed: {exc}")
        ctx["result"]["barcodes"] = []
        ctx["result"]["barcode_count"] = 0

    await orchestrator.update_progress(ctx, 70, "Barcode recognition completed")


async def nlp_step(ctx: PipelineContext) -> None:
    options = ctx["options"]
    if not options.get("enable_nlp", True):
        return

    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)

    engine_name = options.get("nlp_engine") or "spacy"
    await orchestrator.update_progress(ctx, 70, f"NLP analysis with {engine_name.title()}...")

    full_text = ctx["result"].get("full_text") or " ".join([b.get("text", "") for b in ctx["result"].get("text_blocks", [])])
    if full_text and orchestrator.services.get("nlp_service"):
        nlp_result = await orchestrator.call_maybe_async(
            orchestrator.services["nlp_service"].analyze_text,
            full_text,
            top_k_keywords=15,
            engine=options.get("nlp_engine"),
        )
        orchestrator.ensure_not_cancelled(ctx)

        ctx["result"]["keywords"] = [kw.get("keyword") for kw in nlp_result.get("keywords", [])]
        ctx["result"]["keywords_detailed"] = nlp_result.get("keywords", [])
        ctx["result"]["entities"] = nlp_result.get("entities", [])
        ctx["result"]["entities_grouped"] = nlp_result.get("entities_grouped", {})
        ctx["result"]["nlp_engines_used"] = nlp_result.get("engines_used")

    await orchestrator.update_progress(ctx, 85, "NLP analysis completed")


async def template_step(ctx: PipelineContext) -> None:
    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    options = ctx["options"]

    template_id = options.get("template_id")
    if template_id and template_id.strip() and template_id.lower() != "null":
        await orchestrator.update_progress(ctx, 85, "Template extraction...")
        try:
            full_text = ctx["result"].get("full_text", "")
            ctx["result"]["template_extraction"] = await orchestrator.call_maybe_async(
                orchestrator.services["template_service"].extract_fields,
                template_id,
                full_text,
                ctx["result"].get("text_blocks"),
                ctx["result"].get("tables"),
                ctx["result"].get("layout", {}).get("elements"),
            )
        except Exception as exc:
            logger.warning(f"Task {ctx['task_id']}: template extraction failed: {exc}")
            ctx["result"]["template_extraction"] = {"error": str(exc)}
        return

    if options.get("enable_nlp", True):
        full_text = ctx["result"].get("full_text", "")
        if full_text:
            await orchestrator.update_progress(ctx, 85, "Auto-detecting template...")
            try:
                auto_result = await orchestrator.call_maybe_async(
                    orchestrator.services["template_service"].auto_extract,
                    full_text,
                    ctx["result"].get("text_blocks"),
                    ctx["result"].get("tables"),
                )
                if auto_result.get("success"):
                    ctx["result"]["template_extraction"] = auto_result.get("result")
                    ctx["result"]["template_matches"] = auto_result.get("matches", [])
            except Exception as exc:
                logger.warning(f"Task {ctx['task_id']}: auto template failed: {exc}")


async def finalize_step(ctx: PipelineContext) -> None:
    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)

    task = ctx["task"]
    task["progress"] = 100
    task["status"] = "completed"
    task["message"] = "Processing completed"
    task["completed_at"] = datetime.now()
    task["result"] = ctx["result"]

    await orchestrator.send_event(ctx["task_id"], "completed", "Processing completed", 100)


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
        }

        steps = [
            ocr_step,
            layout_step,
            table_step,
            barcode_step,
            nlp_step,
            template_step,
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
