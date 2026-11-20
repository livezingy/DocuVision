"""Batch management routes: create / list / detail / start / pause / resume /
cancel / delete / retry (9 routes).

Moved verbatim from main.py (v1.8.2 C3), including the ``_pipeline_services``
and ``_batch_process_file`` helpers that only these routes use. No ``prefix`` on
the APIRouter — paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from loguru import logger

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
from app.orchestration.single_file_pipeline import run_single_file_pipeline

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


async def _dispatch_batch_completed_webhook(payload: Dict[str, Any]) -> None:
    """Notify ``batch.completed`` subscribers.

    Injected as ``BatchService.on_complete`` (S1 batch 8): the routers layer may
    import any service, so the webhook import that used to live inside
    ``_process_batch`` moves here and the services-layer batch->infra frozen
    edge dissolves. Failures are swallowed to a debug log — dispatch issues
    must never affect batch final state.
    """
    try:
        from app.services.webhook_service import webhook_registry

        await webhook_registry.dispatch_event_async("batch.completed", payload)
    except Exception as exc:
        logger.debug(f"Batch webhook dispatch skipped: {exc}")


async def _dispatch_batch_sheets_export(payload: Dict[str, Any]) -> None:
    """Direct-write the finished batch's mapping-result rows to Google Sheets
    (R-003/P-042 T3, AC2).

    Opt-in per batch via ``options.sheets_export`` (``spreadsheet_id`` +
    optional ``worksheet``, default ``MappedRows``); credentials come from the
    operator machine's settings (``GOOGLE_SERVICE_ACCOUNT_FILE`` /
    ``GOOGLE_APPLICATION_CREDENTIALS`` alias) and travel by parameter only —
    never into logs. Execution model: gspread is synchronous (several HTTPS
    round-trips per export), so the export runs off the event loop via
    ``asyncio.to_thread`` — an inline call here would stall every concurrent
    request on this worker for the duration (review round 1). Failures are
    swallowed to a debug log: export issues must never affect batch final
    state (same fire-and-forget + swallow semantics as the webhook dispatch).
    """
    try:
        from app.core.config import settings
        from app.services.sheets_export_service import DEFAULT_WORKSHEET, export_batch_to_sheets

        credentials_file = str(settings.GOOGLE_SERVICE_ACCOUNT_FILE or "").strip()
        if not credentials_file:
            return
        batch = batch_service.get_batch(str(payload.get("batch_id") or ""))
        if batch is None:
            return
        sheets_cfg = (batch.options or {}).get("sheets_export")
        if not isinstance(sheets_cfg, dict):
            return
        spreadsheet_id = str(sheets_cfg.get("spreadsheet_id") or "").strip()
        if not spreadsheet_id:
            return
        worksheet_name = str(sheets_cfg.get("worksheet") or "").strip() or DEFAULT_WORKSHEET
        summary = await asyncio.to_thread(
            export_batch_to_sheets,
            batch,
            credentials_file=credentials_file,
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name,
        )
        logger.debug(f"Batch sheets export done: {summary}")
    except Exception as exc:
        logger.debug(f"Batch sheets export skipped: {exc}")


async def _dispatch_batch_per_order_export(payload: Dict[str, Any]) -> None:
    """Split the finished batch into per-order CSV files (R-003/P-042 T5, AC6).

    Opt-in per batch via ``options.per_order=True``; target directory from
    ``options.per_order_output_dir``, falling back to
    ``<settings.OUTPUT_DIR>/per_order/<batch_id>`` (ERP watch semantics); the
    directory is re-confined here through ``resolve_per_order_output_dir`` —
    batch creation already rejects escapes with 422, this is belt-and-braces
    for options mutated through other paths.
    Local small-file writes, but still dispatched off the event loop via
    ``asyncio.to_thread`` (review round 1: one execution model for both
    export dispatches). Failures are swallowed to a debug log — export
    issues must never affect batch final state (same contract as the
    webhook/Sheets dispatch).
    """
    try:
        from app.services.per_order_export_service import (
            export_batch_per_order,
            resolve_per_order_output_dir,
        )

        batch = batch_service.get_batch(str(payload.get("batch_id") or ""))
        if batch is None:
            return
        opts = batch.options or {}
        if not opts.get("per_order"):
            return
        output_dir = resolve_per_order_output_dir(
            str(opts.get("per_order_output_dir") or ""),
            str(batch.batch_id),
            settings.OUTPUT_DIR,
        )
        summary = await asyncio.to_thread(export_batch_per_order, batch, output_dir)
        logger.debug(f"Batch per-order export done: {summary}")
    except Exception as exc:
        logger.debug(f"Batch per-order export skipped: {exc}")


async def _on_batch_completed(payload: Dict[str, Any]) -> None:
    """Composed ``batch.completed`` hook: webhook dispatch + opt-in Sheets
    direct-write + opt-in per-order CSV split (routers may import any
    service — no services-layer edge)."""
    await _dispatch_batch_completed_webhook(payload)
    await _dispatch_batch_sheets_export(payload)
    await _dispatch_batch_per_order_export(payload)


def _confine_per_order_dir(opts: Dict[str, Any]) -> None:
    """R-003/P-042 hardening (consumed by R-004 watch-dir flows): the batch
    API is callable by external automation (n8n), so a caller-chosen
    ``per_order_output_dir`` must stay under ``settings.OUTPUT_DIR`` —
    otherwise it is an arbitrary file-write primitive. Confined here at
    creation time (HTTP 422 on escape): the completion dispatch is
    fire-and-forget and cannot report back. The resolved (absolute,
    inside-base) value is written back so the dispatch never sees a raw
    unvalidated path."""
    raw = str(opts.get("per_order_output_dir") or "").strip()
    if not raw:
        return
    from app.services.per_order_export_service import resolve_per_order_output_dir

    try:
        opts["per_order_output_dir"] = resolve_per_order_output_dir(
            raw, "", settings.OUTPUT_DIR
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    _confine_per_order_dir(opts)

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
        await batch_service.start_batch(batch_id, _batch_process_file, on_complete=_on_batch_completed)
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
        success = await batch_service.resume_batch(batch_id, process_func=_batch_process_file, on_complete=_on_batch_completed)
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
