"""Batch management routes: create / list / detail / start / pause / resume /
cancel / delete / retry (9 routes).

Moved verbatim from main.py (v1.8.2 C3), including the ``_pipeline_services``
and ``_batch_process_file`` helpers that only these routes use. No ``prefix`` on
the APIRouter — paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.core.debug_utils import save_debug_overlay_image
from app.core.runtime import (
    _build_page_image_meta,
    _resolve_kie_query_fields_in_options,
    batch_service,
    call_maybe_async,
    formula_service,
    kie_service,
    layout_service,
    ocr_service,
    seal_service,
    table_service,
)
from app.services.batch_service import BatchStatus
from app.services.single_file_pipeline import run_single_file_pipeline

router = APIRouter()

_PIPELINE_SERVICES = None


def _pipeline_services() -> Dict[str, Any]:
    global _PIPELINE_SERVICES
    if _PIPELINE_SERVICES is None:
        _PIPELINE_SERVICES = {
            "ocr_service": ocr_service,
            "layout_service": layout_service,
            "table_service": table_service,
            "formula_service": formula_service,
            "seal_service": seal_service,
            "kie_service": kie_service,
        }
    return _PIPELINE_SERVICES


async def _batch_process_file(file_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """Full orchestrator pipeline for one batch file."""
    opts = dict(options)
    _resolve_kie_query_fields_in_options(opts)
    doc_type_norm = str(opts.get("document_type", "auto") or "auto").strip().lower()
    if doc_type_norm in {"invoice", "receipt", "id_card"} and not opts.get("enable_kie", False):
        opts["enable_kie"] = True

    async def _noop_event(*_args, **_kwargs):
        return None

    return await run_single_file_pipeline(
        file_path,
        opts,
        services=_pipeline_services(),
        call_maybe_async=call_maybe_async,
        send_event=_noop_event,
        build_page_image_meta=_build_page_image_meta,
        save_debug_overlay=save_debug_overlay_image if settings.ENABLE_DEBUG_OVERLAYS else None,
    )


@router.post("/api/v1/batch")
async def create_batch(
    name: str = Form(...),
    files: List[UploadFile] = File(...),
    options: str = Form("{}")
):
    """Create a new batch job"""
    import json

    try:
        opts = json.loads(options)
    except Exception:
        opts = {}

    if not isinstance(opts, dict):
        opts = {}
    _resolve_kie_query_fields_in_options(opts)

    # Save files and create file list
    batch_dir = os.path.join(settings.UPLOAD_DIR, "batch_" + str(uuid.uuid4())[:8])
    os.makedirs(batch_dir, exist_ok=True)

    file_list = []
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:
            continue

        file_path = os.path.join(batch_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        file_list.append({
            "file_path": file_path,
            "file_name": file.filename
        })

    if not file_list:
        raise HTTPException(status_code=400, detail="No valid files provided")

    doc_type_norm = str(opts.get("document_type", "auto") or "auto").strip().lower()
    if doc_type_norm in {"invoice", "receipt", "id_card"} and not opts.get("enable_kie", False):
        opts["enable_kie"] = True
    if "kie_pages" not in opts:
        opts["kie_pages"] = "1"

    batch = batch_service.create_batch(name, file_list, opts)
    return batch.to_dict()


@router.get("/api/v1/batch")
async def list_batches(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List all batch jobs"""
    batch_status = BatchStatus(status) if status else None
    batches = batch_service.list_batches(batch_status, limit, offset)
    return {"batches": batches, "total": len(batch_service.batches)}


@router.get("/api/v1/batch/{batch_id}")
async def get_batch(batch_id: str):
    """Get batch job details"""
    batch = batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch.to_dict()


@router.post("/api/v1/batch/{batch_id}/start")
async def start_batch(batch_id: str, background_tasks: BackgroundTasks):
    """Start processing a batch job"""
    batch = batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    try:
        await batch_service.start_batch(batch_id, _batch_process_file)
        return {"message": "Batch started", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/v1/batch/{batch_id}/pause")
async def pause_batch(batch_id: str):
    """Pause a running batch"""
    try:
        success = await batch_service.pause_batch(batch_id)
        return {"message": "Batch paused" if success else "Cannot pause", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/v1/batch/{batch_id}/resume")
async def resume_batch(batch_id: str):
    """Resume a paused batch"""
    try:
        success = await batch_service.resume_batch(batch_id, process_func=_batch_process_file)
        return {"message": "Batch resumed" if success else "Cannot resume", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/v1/batch/{batch_id}/cancel")
async def cancel_batch(batch_id: str):
    """Cancel a batch job"""
    try:
        success = await batch_service.cancel_batch(batch_id)
        return {"message": "Batch cancelled" if success else "Cannot cancel", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/api/v1/batch/{batch_id}")
async def delete_batch(batch_id: str):
    """Delete a batch job"""
    try:
        success = batch_service.delete_batch(batch_id)
        if not success:
            raise HTTPException(status_code=404, detail="Batch not found")
        return {"message": "Batch deleted", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/v1/batch/{batch_id}/retry")
async def retry_batch_failed(batch_id: str):
    """Retry failed tasks in a batch"""
    try:
        retried = batch_service.retry_failed_tasks(batch_id)
        return {"message": f"Reset {retried} tasks for retry", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
