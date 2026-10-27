"""Pipeline kie steps — split from document_pipeline_orchestrator.py (runs/split batch 3).

Step bodies moved verbatim (tier A); only this import header is new (tier B).
The orchestrator class import is TYPE_CHECKING-only (annotations stay strings).
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from loguru import logger
from app.core.config import settings
from app.services.kie.field_merge import backfill_schema_keys, merge_kie_fields, sum_items_count
from app.services.kie.text_first import build_text_first_payloads, resolve_pages_text_first, text_first_enabled
from app.services.pdf_raster import pdf_page_count, rasterize_pdf_page
if TYPE_CHECKING:
    from app.orchestration.document_pipeline_orchestrator import DocumentPipelineOrchestrator
PipelineContext = Dict[str, Any]


def _base_schema_keys(document_type: str) -> List[str]:
    """Return the base KIE schema key names for a supported doc-type.

    Used to backfill missing scalar keys (never-omit contract) when no
    query_fields are present (merged_schema is None). Lazily imported to keep
    this module's import surface minimal.
    """
    from app.services.kie.query_fields import load_base_schema

    schema = load_base_schema(document_type)
    return [str(k) for k in schema.keys()]


async def kie_step(ctx: PipelineContext) -> None:
    options = ctx["options"]
    if not options.get("enable_kie", False):
        return

    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)

    document_type = str(options.get("document_type", "auto") or "auto").strip().lower()
    from app.services.kie.query_fields import KIE_SUPPORTED_DOC_TYPES

    supported_doc_types = KIE_SUPPORTED_DOC_TYPES

    query_fields: List[Dict[str, str]] = list(options.get("kie_query_fields") or [])
    merged_schema = options.get("kie_merged_schema")
    if query_fields and merged_schema is None:
        from app.services.kie.query_fields import QueryFieldsError, validate_and_prepare_query_fields

        try:
            query_fields, merged_schema = validate_and_prepare_query_fields(
                document_type,
                query_fields,
            )
            options["kie_query_field_names"] = [s["name"] for s in query_fields]
            options["kie_merged_schema"] = merged_schema
        except QueryFieldsError as exc:
            ctx["result"]["kie_fields"] = {}
            ctx["result"]["kie_meta"] = {
                "attempted": True,
                "succeeded": False,
                "stage": "invalid_query_fields",
                "error_code": exc.error_code,
                "error_message": str(exc),
            }
            logger.warning(
                "KIE step skipped | task_id={} | stage=invalid_query_fields | error_code={} | error={}",
                ctx.get("task_id", ""),
                exc.error_code,
                exc,
            )
            await orchestrator.update_progress(ctx, 80, "KIE skipped | invalid_query_fields")
            return

    if document_type not in supported_doc_types:
        ctx["result"]["kie_fields"] = {}
        # Distinguish "auto" (user left default, KIE cannot run without an
        # explicit type) from genuinely unsupported values. Both skip KIE,
        # but the error_code must be legible so callers/UI can tell the user
        # what to fix instead of a generic "unsupported" message.
        if document_type == "auto":
            error_code = "auto_document_type_requires_explicit_choice"
            # D2 (P-030 X7): derive the type list from the frozenset so future
            # additions cannot drift from this message.
            supported_list = "/".join(sorted(supported_doc_types))
            error_message = (
                "document_type='auto' cannot run KIE; select a specific "
                f"document_type ({supported_list}) to enable KIE."
            )
            stage = "skipped_auto_doc_type"
        else:
            error_code = "unsupported_document_type"
            error_message = f"document_type '{document_type}' is not supported for KIE"
            stage = "skipped_doc_type"
        ctx["result"]["kie_meta"] = {
            "attempted": True,
            "succeeded": False,
            "stage": stage,
            "error_code": error_code,
            "error_message": error_message,
        }
        logger.warning(
            "KIE step skipped | task_id={} | document_type={} | stage={} | error_code={}",
            ctx.get("task_id", ""),
            document_type,
            stage,
            error_code,
        )
        await orchestrator.update_progress(ctx, 80, f"KIE skipped | {error_code} document_type={document_type}")
        return

    services = getattr(orchestrator, "services", {}) if hasattr(orchestrator, "services") else {}
    kie_service = services.get("kie_service") if isinstance(services, dict) else None
    if kie_service is None:
        logger.warning(
            "KIE step skipped | task_id={} | document_type={} | stage=service_unavailable | error_code=service_unavailable | detail=kie_service_missing",
            ctx.get("task_id", ""),
            document_type,
        )
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

    # Prepare richer inputs for KIE; record them for traceability
    _task = ctx.get("task")
    if not isinstance(_task, dict):
        _task = {}
    layout = ctx["result"].get("layout", {}) if isinstance(ctx["result"].get("layout"), dict) else {}
    preprocessed_image_path = _task.get("preprocessed_image_path")
    if not preprocessed_image_path and isinstance(layout, dict):
        prep_from_layout = layout.get("preprocessed_image_path")
        if isinstance(prep_from_layout, str) and prep_from_layout.strip():
            preprocessed_image_path = prep_from_layout.strip()
    table_meta = ctx["result"].get("table_extraction_meta", {}) if isinstance(ctx["result"].get("table_extraction_meta"), dict) else {}
    tables = ctx["result"].get("tables", []) if isinstance(ctx["result"].get("tables"), list) else []

    ctx["result"]["kie_input"] = {
        "file_path": ctx.get("file_path"),
        "preprocessed_image_path": preprocessed_image_path,
        "layout_present": bool(layout), "table_meta": table_meta,
        "tables_count": len(tables),
    }

    _tid = str(ctx.get("task_id", "") or "")
    _pp = preprocessed_image_path if isinstance(preprocessed_image_path, str) else ""
    _pp_ok = bool(_pp and os.path.isfile(_pp))
    logger.info(
        "KIE step start | task_id={} | document_type={} | preprocessed_image_ok={} | tables_count={}",
        _tid,
        document_type,
        _pp_ok,
        len(tables) if isinstance(tables, list) else 0,
    )

    file_path = str(ctx.get("file_path") or "")
    is_pdf = os.path.splitext(file_path)[1].lower() == ".pdf"
    page_count = pdf_page_count(file_path) if is_pdf else 1
    pages_spec = options.get("kie_pages")
    tf_active = text_first_enabled(document_type, is_pdf)
    selected_pages, pages_truncated = resolve_pages_text_first(pages_spec, page_count, settings.KIE_MAX_PAGES, text_first=tf_active, layout=layout)
    multipage = is_pdf and len(selected_pages) > 1
    tf_payloads = {}
    if tf_active:
        # Same-source P-032 contract: the grounding layer is injected here (L2 may
        # consume any service) — kie.text_first stays free of the evidence import
        # and the frozen kie->evidence edge dissolves (runs/split batch 3).
        from app.services.evidence.grounding import (
            grounding_source,
            trusted_grounding_page_set,
        )

        tf_payloads = build_text_first_payloads(
            layout,
            selected_pages,
            blocks_by_page=grounding_source(file_path).blocks,
            trusted_pages=trusted_grounding_page_set(file_path),
        )

    await orchestrator.update_progress(ctx, 79, "KIE: preparing model and inputs...")
    t_kie0 = time.perf_counter()
    fields_by_page: Dict[str, Dict[str, Any]] = {}
    confidence_values: List[float] = []
    total_infer_ms = 0
    total_model_load_ms = 0
    last_metadata: Dict[str, Any] = {}
    temp_rasters: List[str] = []

    async def _extract_one_page(page_num: int, vl_image_path: Optional[str]) -> Dict[str, Any]:
        prep = preprocessed_image_path if page_num == 1 else None
        if vl_image_path or page_num in tf_payloads:
            prep = None
        return await orchestrator.call_maybe_async(
            kie_service.extract_fields,
            file_path,
            document_type,
            preprocessed_image_path=prep,
            layout=layout, table_meta=table_meta, tables=tables,
            query_fields=query_fields or None,
            merged_schema=merged_schema,
            vl_image_path=vl_image_path,
            page_number=page_num,
            text_payload=tf_payloads.get(page_num),
        )

    try:
        for page_num in selected_pages:
            await orchestrator.update_progress(
                ctx, 79, f"KIE: inference running (page {page_num}/{selected_pages[-1]})..."
            )
            vl_path = temp_path = None
            if is_pdf:
                if page_num == 1 and _pp_ok and preprocessed_image_path or page_num in tf_payloads:
                    vl_path = None
                else:
                    raster_path, temp_path = rasterize_pdf_page(file_path, page_num, matrix_scale=2.0)
                    if temp_path:
                        vl_path = raster_path
                        temp_rasters.append(temp_path)
            kie_result = await _extract_one_page(page_num, vl_path)
            page_fields = {}
            if isinstance(kie_result, dict):
                page_fields = kie_result.get("fields", {}) if isinstance(kie_result.get("fields", {}), dict) else {}
                try:
                    confidence_values.append(float(kie_result.get("confidence_avg", 0.0) or 0.0))
                except (TypeError, ValueError):
                    pass
                if isinstance(kie_result.get("metadata"), dict):
                    meta = kie_result["metadata"]
                    last_metadata = meta
                    total_infer_ms += int(meta.get("infer_ms", 0) or 0)
                    total_model_load_ms = max(
                        total_model_load_ms,
                        int(meta.get("kie_model_load_ms", 0) or 0),
                    )
            fields_by_page[str(page_num)] = page_fields
    except Exception as exc:
        for tmp in temp_rasters:
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            except OSError:
                pass
        logger.warning(
            "KIE extraction failed | task_id={} | document_type={} | stage=runtime_error | error={}",
            ctx.get("task_id", ""),
            document_type,
            exc,
        )
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
    finally:
        for tmp in temp_rasters:
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            except OSError:
                pass

    if multipage:
        fields = merge_kie_fields(fields_by_page)
        ctx["result"]["kie_fields_by_page"] = fields_by_page
    else:
        fields = fields_by_page.get(str(selected_pages[0]), {}) if fields_by_page else {}

    # P-034 P0: never-omit backfill — scoped to the text-first channel, where
    # the round-3 observation was made (text-first coi omitting carrier/limits).
    # Legacy-channel output stays byte-identical to main (X3 zero-behavior
    # anchor); scoping also keeps date/currency validation semantics untouched
    # for full-HITL doc types (an absent key must stay "unvalidated", not become
    # a failing empty value — caught by test_kie_return_raw_contract on cloud).
    if tf_active:
        schema_keys = (
            list(merged_schema.keys())
            if isinstance(merged_schema, dict)
            else _base_schema_keys(document_type)
        )
        fields = backfill_schema_keys(fields, schema_keys)

    items_count = sum_items_count(fields) if multipage else int(
        last_metadata.get("items_count", 0) or 0
    )
    if not items_count:
        items_count = sum_items_count(fields)

    confidence_avg = (
        sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    )
    kie_wall_ms = int((time.perf_counter() - t_kie0) * 1000)
    pages_requested = str(pages_spec or "1").strip() or "1"

    ctx["result"]["kie_fields"] = fields
    from app.services.hitl_policy import resolve_hitl_policy
    from app.services.kie.field_validation import validate_kie_fields

    policy = resolve_hitl_policy(options)
    validation = validate_kie_fields(fields, policy.validation_rules)
    ctx["result"]["kie_validation"] = validation
    if policy.should_enqueue(validation, options.get("enable_hitl", True)):
        from app.services.hitl_queue import hitl_queue

        await hitl_queue.enqueue(
            str(ctx.get("task_id", "")),
            str(ctx["task"].get("file_name", "")),
            "kie_validation_failed",
            {
                "validation": validation,
                "fields": fields,
                "hitl_profile": policy.profile,
                "schema_fields": list(policy.schema_field_names),
            },
        )
    ctx["result"]["kie_meta"] = {
        "attempted": True,
        "succeeded": True,
        "stage": "completed",
        "error_code": "",
        "error_message": "",
        "confidence_avg": confidence_avg,
        "items_count": items_count,
        "items_source": str(last_metadata.get("items_source", "n/a")),
        "kie_model_load_ms": total_model_load_ms,
        "kie_infer_ms": total_infer_ms,
        "kie_wall_ms": kie_wall_ms,
        "ocr_text_length": 0,
        "engine": str(last_metadata.get("engine", "") or "qwen2.5-vl"),
        "kie_query_fields_requested": list(options.get("kie_query_field_names") or []),
        "kie_query_fields_count": int(last_metadata.get("kie_query_fields_count", 0) or 0),
        "kie_pages_requested": pages_requested,
        "kie_pages_processed": selected_pages,
        "kie_pages_truncated": pages_truncated,
        "kie_multipage_merge": multipage,
        "resolved_document_type": document_type,
    }
    logger.info(
        "KIE step completed | task_id={} | document_type={} | fields_count={} | pages={} | multipage={}",
        str(ctx.get("task_id", "") or ""),
        document_type,
        len(fields),
        selected_pages,
        multipage,
    )
    await orchestrator.update_progress(
        ctx, 80, f"KIE extraction completed | fields={len(fields)} | pages={len(selected_pages)}"
    )
