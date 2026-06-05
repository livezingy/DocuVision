"""Run full document pipeline for one file (analyze + batch)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Callable, Awaitable, Dict, Optional

from app.orchestration.document_pipeline_orchestrator import DocumentPipelineOrchestrator


async def run_single_file_pipeline(
    file_path: str,
    options: Dict[str, Any],
    *,
    services: Dict[str, Any],
    call_maybe_async: Callable[..., Awaitable[Any]],
    send_event: Optional[Callable[..., Awaitable[None]]] = None,
    build_page_image_meta: Optional[Callable[..., Dict[str, Any]]] = None,
    save_debug_overlay: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """
    Execute DocumentPipelineOrchestrator for one file without registering in global tasks.

    Returns the task result dict (layout, kie_fields, view via envelope merge, quality, etc.).
    """
    task_id = str(uuid.uuid4())
    file_name = os.path.basename(file_path)

    async def _noop_event(*_args, **_kwargs):
        return None

    orchestrator = DocumentPipelineOrchestrator(
        services=services,
        send_event=send_event or _noop_event,
        is_cancelled=lambda _tid: False,
        call_maybe_async=call_maybe_async,
        build_page_image_meta=build_page_image_meta,
        save_debug_overlay=save_debug_overlay,
    )

    task = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "Batch item",
        "created_at": datetime.now(),
        "completed_at": None,
        "file_path": file_path,
        "file_name": file_name,
        "options": dict(options),
        "result": None,
    }

    await orchestrator.run(task_id, task)
    result = task.get("result") or {}
    if not isinstance(result, dict):
        result = {}
    result.setdefault("document_info", {})
    if isinstance(result["document_info"], dict):
        result["document_info"].setdefault("file_name", file_name)
        result["document_info"].setdefault("processed_at", datetime.now().isoformat())
    if task.get("status") == "failed":
        raise RuntimeError(task.get("message") or "pipeline failed")
    return result
