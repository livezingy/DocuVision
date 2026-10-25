"""Document processing pipeline orchestrator.

This module owns pipeline sequencing and task state progression.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from loguru import logger


from app.orchestration.steps import (  # noqa: F401 (re-export; step bodies live in steps/, batch 3)
    evidence_step,
    figure_step,
    finalize_step,
    formula_step,
    kie_step,
    layout_step,
    phase1_envelope_step,
    pii_mask_step,
    seal_step,
    table_step,
)

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
        from app.services.persistence.analyze_job_store import persist_task_safe

        await persist_task_safe(task)

        from app.services.file_type_detector import detect_file_type

        detected_type, _detect_pages = detect_file_type(task["file_path"])
        result: Dict[str, Any] = {
            "document_info": {
                "file_name": task["file_name"],
                "pages": 0,
                "processed_at": datetime.now().isoformat(),
                "detected_file_type": detected_type.value,
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
            figure_step,  # Crop figure regions + split-figure integrity checks (GLM trial P0-2)
            table_step,
            kie_step,
            formula_step,
            seal_step,
            phase1_envelope_step,  # Build Phase 1 Envelope (preprocessing, raw, fused, view, quality)
            evidence_step,  # P-029: optional evidence gate (EVIDENCE_ENABLED, default off)
            pii_mask_step,  # P-030a: optional exit PII mask (enable_pii_mask, default off)
            finalize_step,
        ]

        try:
            for step in steps:
                await step(ctx)
        except asyncio.CancelledError:
            task["status"] = "cancelled"
            task["message"] = "Task cancelled"
            from app.services.persistence.analyze_job_store import persist_task_safe

            await persist_task_safe(task)
            await self.send_event(task_id, "cancelled", "Task cancelled")
            return
        except Exception as exc:
            logger.error(f"Task failed: {task_id} | File: {task.get('file_name', 'unknown')} | Error: {exc}")
            logger.exception(exc)
            task["status"] = "failed"
            task["message"] = f"Processing failed: {exc}"
            from app.services.persistence.analyze_job_store import persist_task_safe

            await persist_task_safe(task)
            return
