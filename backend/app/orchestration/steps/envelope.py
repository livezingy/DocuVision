"""Pipeline envelope steps — split from document_pipeline_orchestrator.py (runs/split batch 3).

Step bodies moved verbatim (tier A); only this import header is new (tier B).
The orchestrator class import is TYPE_CHECKING-only (annotations stay strings).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from loguru import logger
from app.core.config import settings
from app.services.kie.kie_field_metrics import count_meaningful_kie_fields, evaluate_kie_id_card_precision, evaluate_kie_production_hit
if TYPE_CHECKING:
    from app.orchestration.document_pipeline_orchestrator import DocumentPipelineOrchestrator
PipelineContext = Dict[str, Any]


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
                        str(b.get("type", "")).lower() in EnvelopeBuilder.SKIP_FORMULA_TYPES
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
            table_backfill=ctx["result"].get("table_backfill"),
        )
        if formula_adapted is not None:
            quality.update(formula_adapted.get("quality_patch", {}))
        if seal_adapted is not None:
            quality.update(seal_adapted.get("quality_patch", {}))

        # Figure export quality metrics (GLM trial P0-2)
        figures_result = ctx["result"].get("figures")
        if isinstance(figures_result, dict):
            quality["figure_count"] = int(figures_result.get("figure_count", 0))
            quality["figure_cropped_count"] = int(figures_result.get("cropped_count", 0))
            quality["figure_integrity_warning_count"] = len(figures_result.get("warnings") or [])

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
        view_fields = view.get("fields", {}) if isinstance(view.get("fields", {}), dict) else {}
        kie_fields_count = count_meaningful_kie_fields(view_fields)
        doc_type_for_kie = str(
            kie_meta.get("resolved_document_type")
            or ctx.get("options", {}).get("document_type", "")
            or ""
        ).strip().lower()
        prod_hit, prod_reason, prod_keys = evaluate_kie_production_hit(doc_type_for_kie, view_fields)
        id_card_prec_hit, id_card_prec_reason, id_card_prec_keys = evaluate_kie_id_card_precision(
            doc_type_for_kie, view_fields
        )
        quality["kie_attempted"] = bool(kie_meta.get("attempted", False))
        quality["kie_stage"] = str(kie_meta.get("stage", ""))
        quality["kie_error_code"] = str(kie_meta.get("error_code", ""))
        quality["kie_error_message"] = str(kie_meta.get("error_message", "") or "")
        quality["kie_fields_count"] = kie_fields_count
        quality["kie_production_hit"] = prod_hit
        quality["kie_production_reason"] = prod_reason
        if prod_keys:
            quality["kie_production_keys"] = prod_keys
        quality["kie_id_card_precision_hit"] = id_card_prec_hit
        quality["kie_id_card_precision_reason"] = id_card_prec_reason
        if id_card_prec_keys:
            quality["kie_id_card_precision_keys"] = id_card_prec_keys
        try:
            quality["kie_items_count"] = int(kie_meta.get("items_count", 0) or 0)
        except (TypeError, ValueError):
            quality["kie_items_count"] = 0
        try:
            quality["kie_confidence_avg"] = float(kie_meta.get("confidence_avg", 0.0) or 0.0)
        except (TypeError, ValueError):
            quality["kie_confidence_avg"] = 0.0
        if quality["kie_attempted"] and kie_meta.get("succeeded") is True:
            quality["kie_confidence_source"] = str(kie_meta.get("engine", "") or "qwen2.5-vl")
        else:
            quality["kie_confidence_source"] = ""
        try:
            quality["kie_model_load_ms"] = int(kie_meta.get("kie_model_load_ms", 0) or 0)
        except (TypeError, ValueError):
            quality["kie_model_load_ms"] = 0
        quality["kie_items_source"] = str(kie_meta.get("items_source", "n/a"))

        from app.services.kie.query_fields import list_filled_query_fields

        opts = ctx.get("options", {}) if isinstance(ctx.get("options"), dict) else {}
        requested_qf = list(opts.get("kie_query_field_names") or [])
        if not requested_qf and isinstance(kie_meta.get("kie_query_fields_requested"), list):
            requested_qf = [str(x) for x in kie_meta["kie_query_fields_requested"]]
        quality["kie_query_fields_requested"] = requested_qf
        quality["kie_query_fields_filled"] = list_filled_query_fields(view_fields, requested_qf)

        if isinstance(kie_meta.get("kie_pages_requested"), str):
            quality["kie_pages_requested"] = kie_meta["kie_pages_requested"]
        if isinstance(kie_meta.get("kie_pages_processed"), list):
            quality["kie_pages_processed"] = kie_meta["kie_pages_processed"]
        if kie_meta.get("kie_pages_truncated") is True:
            quality["kie_pages_truncated"] = True
        if kie_meta.get("kie_multipage_merge") is True:
            quality["kie_multipage_merge"] = True

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

        # Figure crop export (GLM trial P0-2): attach the public figures dict
        # (crop URLs + split warnings) to the envelope. JobEnvelope.figures
        # is Optional, so runs without figures simply omit the key.
        figures_result = ctx["result"].get("figures")
        if isinstance(figures_result, dict) and (
            figures_result.get("items") or figures_result.get("warnings") or figures_result.get("errors")
        ):
            envelope_dict["figures"] = figures_result
        ctx["task"]["envelope"] = envelope_dict

        await orchestrator.update_progress(ctx, 90, "Phase 1 Envelope built")

    except Exception as e:
        logger.error(f"Task {task_id}: Phase 1 envelope building failed: {e}")
        logger.exception(e)
        raise
