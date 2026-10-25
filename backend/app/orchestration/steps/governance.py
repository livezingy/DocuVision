"""Pipeline governance steps — split from document_pipeline_orchestrator.py (runs/split batch 3).

Step bodies moved verbatim (tier A); only this import header is new (tier B).
The orchestrator class import is TYPE_CHECKING-only (annotations stay strings).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict
from loguru import logger
from app.services.document_info_utils import resolve_document_page_count
if TYPE_CHECKING:
    from app.orchestration.document_pipeline_orchestrator import DocumentPipelineOrchestrator
PipelineContext = Dict[str, Any]


async def evidence_step(ctx: PipelineContext) -> None:
    """P-029 L5: optional evidence gate (default off via EVIDENCE_ENABLED).

    Runs after the envelope so quote grounding can use the fused layer's
    per-page text; verifies PICO findings fail-closed and routes near_match
    / slot findings to HITL (see services/evidence/gate.py).
    """
    from app.core.config import settings

    if not getattr(settings, "EVIDENCE_ENABLED", False):
        return
    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)
    await orchestrator.update_progress(ctx, 90, "Evidence verification (gate A/B/C)...")
    from app.services.evidence.gate import run_evidence_gate

    ctx["result"]["evidence"] = await run_evidence_gate(ctx)


async def pii_mask_step(ctx: PipelineContext) -> None:
    """P-030a: optional exit PII mask (enable_pii_mask, default off).

    Runs after the evidence gate (its verdict is already written) and before
    finalize so nothing unmasked reaches persist_task_safe. Field-level scope:
    rewrites tax-id variants in the result tree in place; the evidence and
    document_info subtrees are never touched. kie_fields is shared by
    reference with the envelope view, so masking propagates to view.fields.
    """
    options = ctx["options"]
    if not options.get("enable_pii_mask", False):
        return
    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)
    from app.services.pii_mask import mask_result_exit

    count = mask_result_exit(ctx["result"])
    # X3: log the count only — never the matched values.
    logger.info(
        "PII mask applied | task_id={} | masked_values={}",
        str(ctx.get("task_id", "") or ""),
        count,
    )
    await orchestrator.update_progress(ctx, 95, f"PII mask applied | values={count}")


async def finalize_step(ctx: PipelineContext) -> None:
    orchestrator: DocumentPipelineOrchestrator = ctx["orchestrator"]
    orchestrator.ensure_not_cancelled(ctx)

    task = ctx["task"]
    task["progress"] = 100
    # Keep "completed" for frontend compatibility; Phase 1 job routes accept both "succeeded" and "completed"
    task["status"] = "completed"
    task["message"] = "Processing completed"
    task["completed_at"] = datetime.now()

    result = ctx["result"]
    doc_info = result.setdefault("document_info", {})
    if isinstance(doc_info, dict):
        doc_info["pages"] = resolve_document_page_count(ctx["file_path"], result)
    # Merge Phase1 envelope view/quality into result for GET /tasks/.../result
    # （含 view.fields 与 formulas/seals；前端 updateExtractView / Formulas 等统一读 result.view）
    envelope = task.get("envelope")
    if isinstance(envelope, dict):
        view = envelope.get("view")
        if isinstance(view, dict) and view:
            result["view"] = view
        quality = envelope.get("quality")
        if isinstance(quality, dict) and quality:
            result["quality"] = quality
        # v1.8.1 §6/D9: expose preprocessing metadata (coordinate_space /
        # angle_deg / use_doc_unwarping) so downstream consumers of the task
        # result (proof pack renderer) can tell which space bboxes live in.
        preprocessing = envelope.get("preprocessing")
        if isinstance(preprocessing, dict) and preprocessing:
            result["preprocessing"] = preprocessing
    task["result"] = result

    from app.services.persistence.analyze_job_store import persist_task_safe

    await persist_task_safe(task)

    await orchestrator.send_event(ctx["task_id"], "completed", "Processing completed", 100)

    try:
        from app.services.webhook_service import webhook_registry

        await webhook_registry.dispatch_event_async(
            "task.completed",
            {
                "task_id": ctx["task_id"],
                "file_name": task.get("file_name"),
                "status": task.get("status"),
                "validation_passed": (result.get("kie_validation") or {}).get("validation_passed"),
            },
        )
    except Exception as hook_exc:
        logger.debug(f"Webhook dispatch skipped: {hook_exc}")
