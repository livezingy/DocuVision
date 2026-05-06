"""Document processing pipeline orchestrator.

This module owns pipeline sequencing and task state progression.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

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


async def table_step(ctx: PipelineContext) -> None:
    options = ctx["options"]
    if not options.get("enable_table", True):
        return

    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)

    engine_name = options.get("table_engine") or "ppstructure"
    allow_fullpage_fallback = bool(options.get("table_allow_fullpage_fallback", False))
    has_layout_result = bool(ctx["result"].get("layout"))
    layout_elements = ctx["result"].get("layout", {}).get("elements", []) if has_layout_result else None
    layout_table_blocks = (
        sum(1 for el in layout_elements if isinstance(el, dict) and el.get("type") == "table")
        if isinstance(layout_elements, list)
        else 0
    )

    if not has_layout_result and not allow_fullpage_fallback:
        logger.warning(
            "Table step boundary warning | layout_missing=true | fullpage_fallback=false | table_step_will_skip=true"
        )

    if has_layout_result and layout_table_blocks == 0 and not allow_fullpage_fallback:
        logger.info(
            "Table step boundary info | layout_tables=0 | fullpage_fallback=false | expected_result=empty_tables"
        )

    await orchestrator.update_progress(
        ctx,
        45,
        (
            f"Trying table extraction with {engine_name.title()} "
            f"(layout-first, full-page fallback={'on' if allow_fullpage_fallback else 'off'})..."
        ),
    )

    ocr_text_blocks = ctx["result"].get("text_blocks") if isinstance(ctx["result"].get("text_blocks"), list) else None
    table_result_wrapper = await orchestrator.call_maybe_async(
        orchestrator.services["table_service"].extract_with_meta,
        ctx["file_path"],
        engine=options.get("table_engine"),
        fallback=True,
        layout_elements=layout_elements,
        ocr_text_blocks=ocr_text_blocks,
        allow_fullpage_fallback=allow_fullpage_fallback,
    )
    orchestrator.ensure_not_cancelled(ctx)

    if isinstance(table_result_wrapper, dict):
        table_result = table_result_wrapper.get("tables", [])
        service_meta = table_result_wrapper.get("meta", {})
    else:
        table_result = table_result_wrapper if isinstance(table_result_wrapper, list) else []
        service_meta = {}

    step_meta = {
        "strategy": "layout_first",
        "engine_requested": engine_name,
        "allow_fullpage_fallback": allow_fullpage_fallback,
        "layout_present": has_layout_result,
        "layout_table_blocks": layout_table_blocks,
        "tables_returned": len(table_result) if isinstance(table_result, list) else 0,
    }
    if isinstance(service_meta, dict):
        step_meta["service"] = service_meta
    ctx["result"]["table_extraction_meta"] = step_meta

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
        ctx["result"]["formula_meta"] = {
            "attempted": True,
            "succeeded": False,
            "stage": "service_unavailable",
            "error_level": "soft",
            "error_code": "service_unavailable",
            "error_message": "formula_service is not available",
        }
        ctx["result"]["formula_stats"] = {}
        return

    layout_result = ctx["result"].get("layout", {}) if isinstance(ctx["result"], dict) else {}
    formula_boxes = _collect_layout_blocks(
        layout_result,
        accepted_types={"formula", "inline_formula", "equation"},
    )
    roi_source_image_path = ctx["task"].get("preprocessed_image_path") or ctx["file_path"]
    logger.info(
        "Formula ROI mode | layout_formula_boxes={} | roi_source_image={}",
        len(formula_boxes),
        roi_source_image_path,
    )

    # Short-circuit when no layout-detected formula boxes to avoid
    # unnecessary lazy initialization of optional formula pipelines.
    if not formula_boxes:
        ctx["result"]["formula_meta"] = {
            "attempted": False,
            "succeeded": False,
            "stage": "no_layout_formula_boxes",
            "error_level": "none",
            "error_code": "",
            "error_message": "",
        }
        ctx["result"]["formula_stats"] = {"formula_count": 0, "layout_formula_box_count": 0}
        return

    formula_result = await orchestrator.call_maybe_async(
        formula_service.recognize,
        ctx["file_path"],
        disable_layout=True if formula_boxes else bool(options.get("formula_disable_layout", False)),
        disable_preprocess=bool(options.get("formula_disable_preprocess", False)),
        layout_formula_boxes=formula_boxes,
        roi_source_image_path=roi_source_image_path,
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
        error_message = "invalid_formula_result"
        error_level = "soft"
        error_code = "invalid_result"
        failure_stage = "inference"
        if isinstance(formula_result, dict):
            error_message = str(formula_result.get("error", error_message))
            error_level = str(formula_result.get("error_level", error_level))
            error_code = str(formula_result.get("error_code", error_code))
            failure_stage = str(formula_result.get("failure_stage", failure_stage))

        ctx["result"]["formula_meta"] = {
            "attempted": True,
            "succeeded": False,
            "stage": failure_stage,
            "error_level": error_level,
            "error_code": error_code,
            "error_message": error_message,
        }
        ctx["result"]["formula_stats"] = formula_result.get("stats", {}) if isinstance(formula_result, dict) else {}
        return

    ctx["result"]["formula_unwrapped_results"] = formula_result.get("unwrapped_results", [])
    ctx["result"]["formula_stats"] = formula_result.get("stats", {})
    ctx["result"]["formula_stage"] = formula_result.get("stage")
    ctx["result"]["formula_layout_boxes"] = formula_boxes
    ctx["result"]["formula_meta"] = {
        "attempted": True,
        "succeeded": True,
        "stage": str(formula_result.get("stage", "single")),
        "error_level": str(formula_result.get("error_level", "none")),
        "error_code": str(formula_result.get("error_code", "")),
        "error_message": "",
    }

    formula_count = int(formula_result.get("stats", {}).get("formula_count", 0))
    await orchestrator.update_progress(ctx, 74, f"Formula recognition completed | Formulas: {formula_count}")


async def chart_step(ctx: PipelineContext) -> None:
    options = ctx["options"]
    if not options.get("enable_chart", False):
        return

    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)
    await orchestrator.update_progress(ctx, 75, "Running chart recognition...")

    chart_service = orchestrator.services.get("chart_service")
    if chart_service is None:
        logger.warning("Chart step enabled but chart_service is not available; skipping")
        ctx["result"]["chart_meta"] = {
            "attempted": True,
            "succeeded": False,
            "stage": "service_unavailable",
            "error_level": "soft",
            "error_code": "service_unavailable",
            "error_message": "chart_service is not available",
        }
        ctx["result"]["chart_stats"] = {}
        return

    layout_result = ctx["result"].get("layout", {}) if isinstance(ctx["result"], dict) else {}
    chart_boxes = _collect_layout_blocks(
        layout_result,
        accepted_types={"chart", "flowchart", "figure_table_chart"},
    )
    roi_source_image_path = ctx["task"].get("preprocessed_image_path") or ctx["file_path"]
    logger.info(
        "Chart ROI mode | layout_chart_boxes={} | roi_source_image={}",
        len(chart_boxes),
        roi_source_image_path,
    )

    # Short-circuit when no layout-detected chart boxes to avoid
    # unnecessary lazy initialization of optional chart pipelines.
    if not chart_boxes:
        ctx["result"]["chart_meta"] = {
            "attempted": False,
            "succeeded": False,
            "stage": "no_layout_chart_boxes",
            "error_level": "none",
            "error_code": "",
            "error_message": "",
        }
        ctx["result"]["chart_stats"] = {"chart_count": 0, "layout_chart_box_count": 0}
        return

    chart_result = await orchestrator.call_maybe_async(
        chart_service.recognize,
        ctx["file_path"],
        layout_chart_boxes=chart_boxes,
        roi_source_image_path=roi_source_image_path,
    )

    if not isinstance(chart_result, dict) or not chart_result.get("ok", False):
        logger.warning(f"Chart recognition skipped or failed: {chart_result}")
        error_message = "invalid_chart_result"
        error_level = "soft"
        error_code = "invalid_result"
        failure_stage = "inference"
        if isinstance(chart_result, dict):
            error_message = str(chart_result.get("error", error_message))
            error_level = str(chart_result.get("error_level", error_level))
            error_code = str(chart_result.get("error_code", error_code))
            failure_stage = str(chart_result.get("failure_stage", failure_stage))

        ctx["result"]["chart_meta"] = {
            "attempted": True,
            "succeeded": False,
            "stage": failure_stage,
            "error_level": error_level,
            "error_code": error_code,
            "error_message": error_message,
        }
        ctx["result"]["chart_stats"] = chart_result.get("stats", {}) if isinstance(chart_result, dict) else {}
        return

    ctx["result"]["chart_unwrapped_results"] = chart_result.get("unwrapped_results", [])
    ctx["result"]["chart_stats"] = chart_result.get("stats", {})
    ctx["result"]["chart_stage"] = chart_result.get("stage")
    ctx["result"]["chart_layout_boxes"] = chart_boxes
    ctx["result"]["chart_meta"] = {
        "attempted": True,
        "succeeded": True,
        "stage": str(chart_result.get("stage", "single")),
        "error_level": str(chart_result.get("error_level", "none")),
        "error_code": str(chart_result.get("error_code", "")),
        "error_message": "",
    }

    chart_count = int(chart_result.get("stats", {}).get("chart_count", 0))
    await orchestrator.update_progress(ctx, 76, f"Chart recognition completed | Charts: {chart_count}")


async def seal_step(ctx: PipelineContext) -> None:
    options = ctx["options"]
    if not options.get("enable_seal", False):
        return

    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)
    await orchestrator.update_progress(ctx, 76, "Running seal recognition...")

    seal_service = orchestrator.services.get("seal_service")
    if seal_service is None:
        logger.warning("Seal step enabled but seal_service is not available; skipping")
        ctx["result"]["seal_meta"] = {
            "attempted": True,
            "succeeded": False,
            "stage": "service_unavailable",
            "error_level": "soft",
            "error_code": "service_unavailable",
            "error_message": "seal_service is not available",
        }
        ctx["result"]["seal_stats"] = {}
        return

    seal_result = await orchestrator.call_maybe_async(
        seal_service.recognize,
        ctx["file_path"],
    )

    if not isinstance(seal_result, dict) or not seal_result.get("ok", False):
        logger.warning(f"Seal recognition skipped or failed: {seal_result}")
        error_message = "invalid_seal_result"
        error_level = "soft"
        error_code = "invalid_result"
        failure_stage = "inference"
        if isinstance(seal_result, dict):
            error_message = str(seal_result.get("error", error_message))
            error_level = str(seal_result.get("error_level", error_level))
            error_code = str(seal_result.get("error_code", error_code))
            failure_stage = str(seal_result.get("failure_stage", failure_stage))

        ctx["result"]["seal_meta"] = {
            "attempted": True,
            "succeeded": False,
            "stage": failure_stage,
            "error_level": error_level,
            "error_code": error_code,
            "error_message": error_message,
        }
        ctx["result"]["seal_stats"] = seal_result.get("stats", {}) if isinstance(seal_result, dict) else {}
        return

    ctx["result"]["seal_unwrapped_results"] = seal_result.get("unwrapped_results", [])
    ctx["result"]["seal_stats"] = seal_result.get("stats", {})
    ctx["result"]["seal_stage"] = seal_result.get("stage")
    ctx["result"]["seal_meta"] = {
        "attempted": True,
        "succeeded": True,
        "stage": str(seal_result.get("stage", "single")),
        "error_level": str(seal_result.get("error_level", "none")),
        "error_code": str(seal_result.get("error_code", "")),
        "error_message": "",
    }

    seal_count = int(seal_result.get("stats", {}).get("seal_count", 0))
    await orchestrator.update_progress(ctx, 78, f"Seal recognition completed | Seals: {seal_count}")


async def kie_step(ctx: PipelineContext) -> None:
    options = ctx["options"]
    if not options.get("enable_kie", False):
        return

    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)
    await orchestrator.update_progress(ctx, 79, "Running KIE extraction...")

    document_type = str(options.get("document_type", "auto") or "auto").strip().lower()
    supported_doc_types = {"invoice", "id_card", "receipt"}
    if document_type not in supported_doc_types:
        ctx["result"]["kie_fields"] = {}
        ctx["result"]["kie_meta"] = {
            "attempted": True,
            "succeeded": False,
            "stage": "skipped_doc_type",
            "error_code": "unsupported_document_type",
            "error_message": f"document_type '{document_type}' is not supported for KIE",
        }
        await orchestrator.update_progress(ctx, 80, f"KIE skipped | unsupported document_type={document_type}")
        return

    services = getattr(orchestrator, "services", {}) if hasattr(orchestrator, "services") else {}
    kie_service = services.get("kie_service") if isinstance(services, dict) else None
    if kie_service is None:
        logger.warning("KIE step enabled but kie_service is not available; skipping")
        ctx["result"]["kie_fields"] = {}
        ctx["result"]["kie_meta"] = {
            "attempted": True,
            "succeeded": False,
            "stage": "service_unavailable",
            "error_code": "service_unavailable",
            "error_message": "kie_service is not available",
        }
        await orchestrator.update_progress(ctx, 80, "KIE extraction skipped (service unavailable)")
        return

    # Prepare richer inputs for KIE: prefer preprocessed image and table meta when available
    preprocessed_image_path = ctx["task"].get("preprocessed_image_path") or ctx.get("file_path")
    layout = ctx["result"].get("layout", {}) if isinstance(ctx["result"].get("layout"), dict) else {}
    table_meta = ctx["result"].get("table_extraction_meta", {}) if isinstance(ctx["result"].get("table_extraction_meta"), dict) else {}
    tables = ctx["result"].get("tables", []) if isinstance(ctx["result"].get("tables"), list) else []

    # Record the inputs used for KIE for traceability
    ctx["result"]["kie_input"] = {
        "file_path": ctx.get("file_path"),
        "preprocessed_image_path": preprocessed_image_path,
        "layout_present": bool(layout),
        "table_meta": table_meta,
        "tables_count": len(tables),
    }

    try:
        # Try calling the extended signature first (backwards-compatible).
        kie_result = await orchestrator.call_maybe_async(
            kie_service.extract_fields,
            ctx["file_path"],
            document_type,
            preprocessed_image_path=preprocessed_image_path,
            layout=layout,
            table_meta=table_meta,
            tables=tables,
        )
    except TypeError:
        # Fallback to legacy signature if the service doesn't accept new kwargs.
        try:
            kie_result = await orchestrator.call_maybe_async(
                kie_service.extract_fields,
                ctx["file_path"],
                document_type,
            )
        except Exception as exc:
            logger.warning(f"KIE extraction failed: {exc}")
            ctx["result"]["kie_fields"] = {}
            ctx["result"]["kie_meta"] = {
                "attempted": True,
                "succeeded": False,
                "stage": "runtime_error",
                "error_code": "runtime_error",
                "error_message": str(exc),
            }
            await orchestrator.update_progress(ctx, 80, "KIE extraction failed")
            return
    except Exception as exc:
        logger.warning(f"KIE extraction failed: {exc}")
        ctx["result"]["kie_fields"] = {}
        ctx["result"]["kie_meta"] = {
            "attempted": True,
            "succeeded": False,
            "stage": "runtime_error",
            "error_code": "runtime_error",
            "error_message": str(exc),
        }
        await orchestrator.update_progress(ctx, 80, "KIE extraction failed")
        return

    # Normalize result shape defensively
    fields = {}
    confidence_avg = 0.0
    items_count = 0
    metadata: Dict[str, Any] = {}
    if isinstance(kie_result, dict):
        fields = kie_result.get("fields", {}) if isinstance(kie_result.get("fields", {}), dict) else {}
        try:
            confidence_avg = float(kie_result.get("confidence_avg", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence_avg = 0.0
        try:
            items_count = int(kie_result.get("items_count", 0) or 0)
        except (TypeError, ValueError):
            items_count = 0
        if isinstance(kie_result.get("metadata"), dict):
            metadata = kie_result.get("metadata") or {}

    ctx["result"]["kie_fields"] = fields
    ctx["result"]["kie_meta"] = {
        "attempted": True,
        "succeeded": True,
        "stage": "completed",
        "error_code": "",
        "error_message": "",
        "confidence_avg": confidence_avg,
        "items_count": items_count,
        "items_source": str(metadata.get("items_source", "n/a")),
        "kie_model_load_ms": int(metadata.get("kie_model_load_ms", 0) or 0),
        "ocr_text_length": int(
            (kie_result.get("debug_input", {}) or {}).get("ocr_text_length", 0)
            if isinstance(kie_result, dict) else 0
        ),
    }
    await orchestrator.update_progress(ctx, 80, f"KIE extraction completed | fields={len(fields)} | items={items_count}")


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

        # 3.1 Merge formula/seal recognition output into fused/view/quality.
        formula_unwrapped_results = ctx["result"].get("formula_unwrapped_results", [])
        seal_unwrapped_results = ctx["result"].get("seal_unwrapped_results", [])
        formula_adapted = None
        seal_adapted = None
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

        if seal_unwrapped_results:
            from app.services.seal_service import adapt_seal_results_for_backend

            first_page_blocks = fused.get("pages", [{}])[0].get("blocks", []) if fused.get("pages") else []
            max_reading_order = len(first_page_blocks)

            seal_adapted = adapt_seal_results_for_backend(
                seal_unwrapped_results,
                page_number=1,
                reading_order_start=max_reading_order + 1,
            )

            if fused.get("pages"):
                page0 = fused["pages"][0]
                existing_blocks = page0.get("blocks", [])
                filtered_blocks = [
                    b for b in existing_blocks
                    if not (
                        str(b.get("type", "")).lower() in {"seal", "stamp"}
                        and str(b.get("processing_status", "")).lower() == "skip_seal"
                    )
                ]
                filtered_blocks.extend(seal_adapted.get("fused_seal_blocks", []))
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
        if seal_adapted is not None:
            view["seals"] = seal_adapted.get("view_seals", [])

        kie_fields = ctx["result"].get("kie_fields", {})
        if isinstance(kie_fields, dict) and kie_fields:
            view["fields"] = kie_fields

        ctx["phase1_view"] = view

        # 5. Build quality layer
        quality = builder.build_quality_layer(
            fused_layer=fused,
            processing_time_ms=processing_time_ms,
            engines_used=["doc_preprocessor", "pp_structure_v3"],
        )
        if formula_adapted is not None:
            quality.update(formula_adapted.get("quality_patch", {}))
        if seal_adapted is not None:
            quality.update(seal_adapted.get("quality_patch", {}))

        formula_meta = ctx["result"].get("formula_meta", {}) if isinstance(ctx["result"].get("formula_meta"), dict) else {}
        formula_stats = ctx["result"].get("formula_stats", {}) if isinstance(ctx["result"].get("formula_stats"), dict) else {}

        formula_attempted = bool(formula_meta.get("attempted", False))
        quality["formula_attempted"] = formula_attempted
        quality["formula_stage"] = str(formula_meta.get("stage", ""))
        quality["formula_error_level"] = str(formula_meta.get("error_level", "none"))
        quality["formula_error_code"] = str(formula_meta.get("error_code", ""))
        quality["formula_error_message"] = str(formula_meta.get("error_message", ""))

        layout_formula_boxes = int(formula_stats.get("layout_formula_box_count", 0) or 0)
        recognized_blocks = int(quality.get("formula_blocks_recognized", 0) or 0)
        total_blocks = int(quality.get("formula_blocks_total", 0) or 0)
        total_blocks = max(total_blocks, layout_formula_boxes, recognized_blocks)
        quality["formula_blocks_total"] = total_blocks
        quality["formula_blocks_failed"] = max(0, total_blocks - recognized_blocks)
        quality["formula_recognition_rate"] = (
            float(recognized_blocks) / float(total_blocks) if total_blocks > 0 else 0.0
        )

        seal_meta = ctx["result"].get("seal_meta", {}) if isinstance(ctx["result"].get("seal_meta"), dict) else {}
        seal_stats = ctx["result"].get("seal_stats", {}) if isinstance(ctx["result"].get("seal_stats"), dict) else {}

        seal_attempted = bool(seal_meta.get("attempted", False))
        quality["seal_attempted"] = seal_attempted
        quality["seal_stage"] = str(seal_meta.get("stage", ""))
        quality["seal_error_level"] = str(seal_meta.get("error_level", "none"))
        quality["seal_error_code"] = str(seal_meta.get("error_code", ""))
        quality["seal_error_message"] = str(seal_meta.get("error_message", ""))

        layout_seal_boxes = int(seal_stats.get("layout_seal_box_count", 0) or 0)
        recognized_seals = int(quality.get("seal_blocks_recognized", 0) or 0)
        total_seals = int(quality.get("seal_blocks_total", 0) or 0)
        total_seals = max(total_seals, layout_seal_boxes, recognized_seals)
        quality["seal_blocks_total"] = total_seals
        quality["seal_blocks_recognized"] = recognized_seals
        quality["seal_count"] = recognized_seals if seal_attempted else int(quality.get("seal_count", 0) or 0)
        quality["seal_recognition_rate"] = (
            float(recognized_seals) / float(total_seals) if total_seals > 0 else 0.0
        )

        kie_meta = ctx["result"].get("kie_meta", {}) if isinstance(ctx["result"].get("kie_meta"), dict) else {}
        kie_fields_count = len(view.get("fields", {})) if isinstance(view.get("fields", {}), dict) else 0
        quality["kie_attempted"] = bool(kie_meta.get("attempted", False))
        quality["kie_stage"] = str(kie_meta.get("stage", ""))
        quality["kie_error_code"] = str(kie_meta.get("error_code", ""))
        quality["kie_fields_count"] = kie_fields_count
        try:
            quality["kie_items_count"] = int(kie_meta.get("items_count", 0) or 0)
        except (TypeError, ValueError):
            quality["kie_items_count"] = 0
        try:
            quality["kie_confidence_avg"] = float(kie_meta.get("confidence_avg", 0.0) or 0.0)
        except (TypeError, ValueError):
            quality["kie_confidence_avg"] = 0.0
        quality["kie_confidence_source"] = "uie-m-base" if quality["kie_attempted"] else ""
        try:
            quality["kie_model_load_ms"] = int(kie_meta.get("kie_model_load_ms", 0) or 0)
        except (TypeError, ValueError):
            quality["kie_model_load_ms"] = 0
        quality["kie_items_source"] = str(kie_meta.get("items_source", "n/a"))

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
        return_raw = bool(ctx.get("options", {}).get("return_raw", False))

        envelope_dict = {
            "job_id": task_id,
            "status": "succeeded",
            "version": "1.0",
            "preprocessing": preprocessing,
            "raw": raw if return_raw else {},
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
            kie_step,
            formula_step,
            chart_step,
            seal_step,
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
