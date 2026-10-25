"""Pipeline extraction steps — split from document_pipeline_orchestrator.py (runs/split batch 3).

Step bodies moved verbatim (tier A); only this import header is new (tier B).
The orchestrator class import is TYPE_CHECKING-only (annotations stay strings).
"""

from __future__ import annotations

import os

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from loguru import logger
from app.core.config import settings
from app.orchestration.envelope_builder import EnvelopeBuilder
from app.orchestration.steps.perception import _collect_layout_blocks  # shared helper (tier B)
from app.services.pdf_raster import rasterize_pdf_page

if TYPE_CHECKING:
    from app.orchestration.document_pipeline_orchestrator import DocumentPipelineOrchestrator
PipelineContext = Dict[str, Any]

# P-040 ②: formula-region label set, single-sourced from EnvelopeBuilder (status
# classification + envelope merge use the same object; test_formula_label_sets.py
# pins the agreement — numbered display formulas join the ROI path here).
FORMULA_LAYOUT_TYPES = EnvelopeBuilder.SKIP_FORMULA_TYPES


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

    # D8: land the layout engine's per-cell confidence on the tables (matched by id).
    from app.services.table_cell_confidence import attach_cell_confidence

    attach_cell_confidence(ctx["result"]["tables"], layout_elements)

    table_template = str(options.get("table_template") or "").strip().lower()
    if not table_template and str(options.get("document_type") or "").lower() == "custom":
        table_template = str(options.get("kie_template") or options.get("template_id") or "").strip().lower()
    if table_template in ("bank_statement", "invoice_line_items"):
        from docuvision_core.processing.table_column_mapping import apply_table_template

        mapped_rows = apply_table_template(ctx["result"]["tables"], table_template)
        ctx["result"]["mapped_table_rows"] = mapped_rows
        ctx["result"]["table_template"] = table_template

    # v1.8 E2: selective cell backfill (table_step tail, CPU-only).
    # Enhancement, never replacement — failures keep vision results.
    try:
        from app.services.table_backfill import backfill_tables

        backfill_enabled = str(options.get("table_text_backfill", "auto")) == "auto"
        # v1.8.1 §6/D10: reuse the envelope's single source of truth so the
        # funnel and the view layer agree on the coordinate space.
        from app.orchestration.envelope_builder import EnvelopeBuilder

        prep_meta = EnvelopeBuilder(settings).build_preprocessing_metadata(
            layout_result=ctx["result"].get("layout") or {},
            use_doc_unwarping=settings.USE_DOC_UNWARPING,
        )
        ctx["result"]["table_backfill"] = backfill_tables(
            ctx["result"]["tables"],
            ctx["file_path"],
            enabled=backfill_enabled,
            debug_dir=settings.DEBUG_OUTPUT_DIR if settings.DEBUG_MODE else None,
            angle_deg=float(prep_meta.get("angle_deg", 0.0) or 0.0),
            use_doc_unwarping=bool(prep_meta.get("use_doc_unwarping", False)),
        )
    except Exception as exc:  # noqa: BLE001 — backfill must not fail the task
        logger.warning(f"Table backfill failed (non-fatal): {exc}")
        ctx["result"]["table_backfill"] = {
            "enabled": False,
            "pages_judged": 0,
            "pages_text_layer_trusted": 0,
            "pages_skipped_preprocessed": 0,
            "cells_candidates": 0,
            "cells_confirmed": 0,
            "cells_backfilled": 0,
            "cells_mismatch": 0,
            "backfill_rate": 0.0,
            "mismatch_rate": 0.0,
            "mismatch_details": [],
            "mismatch_details_truncated": 0,
            "page_verdicts": [],
        }

    await orchestrator.update_progress(ctx, 65, f"Table extraction completed | Tables: {len(ctx['result']['tables'])}")


def _merge_formula_stats(merged: Dict[str, Any], stats: Dict[str, Any]) -> None:
    """Sum one recognize() stats dict into the aggregate (counts add, label_hist
    dict-merges, first non-empty first_formula wins)."""
    for key in ("formula_count", "layout_formula_box_count", "roi_total", "roi_recognized"):
        if key in stats:
            merged[key] = int(merged.get(key, 0)) + int(stats[key] or 0)
    for label, count in (stats.get("label_hist") or {}).items():
        hist = merged.setdefault("label_hist", {})
        hist[label] = int(hist.get(label, 0)) + int(count or 0)
    if merged.get("first_formula") is None and stats.get("first_formula"):
        merged["first_formula"] = stats["first_formula"]


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
        accepted_types=FORMULA_LAYOUT_TYPES,
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

    # P-040 ①: page-aware ROI. PDF inputs never carry a preprocessed page image
    # (the layout PDF branch renders pages internally at fitz 2x and deletes
    # them), so each page group re-rasterizes its own page via the pdf_raster
    # shared leaf at the same matrix_scale=2.0 — the frame the PDF-branch
    # element bboxes live in. Image inputs keep the preprocessed||original
    # chain (single page, behaviour unchanged).
    boxes_by_page: Dict[int, List[Dict[str, Any]]] = {}
    for box in formula_boxes:
        boxes_by_page.setdefault(int(box.get("page", 1) or 1), []).append(box)
    is_pdf = str(ctx["file_path"] or "").lower().endswith(".pdf")
    logger.info(
        "Formula ROI mode | layout_formula_boxes={} | pages={} | input_pdf={}",
        len(formula_boxes),
        sorted(boxes_by_page.keys()),
        is_pdf,
    )

    unwrapped_all: List[Any] = []
    merged_stats: Dict[str, Any] = {}
    first_failure: Optional[Dict[str, Any]] = None
    any_ok = False
    for page_num in sorted(boxes_by_page.keys()):
        roi_tmp_path: Optional[str] = None
        if is_pdf:
            roi_path, roi_tmp_path = rasterize_pdf_page(
                ctx["file_path"], page_num, matrix_scale=2.0
            )
        else:
            roi_path = ctx["task"].get("preprocessed_image_path") or ctx["file_path"]
        try:
            page_result = await orchestrator.call_maybe_async(
                formula_service.recognize,
                ctx["file_path"],
                disable_layout=True,
                disable_preprocess=bool(options.get("formula_disable_preprocess", False)),
                layout_formula_boxes=boxes_by_page[page_num],
                roi_source_image_path=roi_path,
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
        finally:
            if roi_tmp_path and os.path.exists(roi_tmp_path):
                try:
                    os.remove(roi_tmp_path)
                except OSError as cleanup_exc:
                    logger.debug(f"Formula ROI page raster cleanup failed: {cleanup_exc}")

        if isinstance(page_result, dict) and page_result.get("ok", False):
            any_ok = True
            unwrapped_all.extend(page_result.get("unwrapped_results", []) or [])
            _merge_formula_stats(merged_stats, page_result.get("stats", {}) or {})
        elif first_failure is None:
            first_failure = page_result if isinstance(page_result, dict) else {}
            logger.warning(f"Formula recognition failed on page {page_num}: {first_failure}")

    if any_ok:
        formula_result = {
            "ok": True,
            "stage": "roi_batch",
            "unwrapped_results": unwrapped_all,
            "stats": merged_stats,
        }
    else:
        formula_result = {
            "ok": False,
            "unwrapped_results": [],
            "stats": merged_stats,
            "error": str(first_failure.get("error", "") or "invalid_formula_result") if first_failure else "invalid_formula_result",
            "error_level": str(first_failure.get("error_level", "soft") or "soft") if first_failure else "soft",
            "error_code": str(first_failure.get("error_code", "invalid_result") or "invalid_result") if first_failure else "invalid_result",
            "failure_stage": str(first_failure.get("failure_stage", "inference") or "inference") if first_failure else "inference",
        }

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
