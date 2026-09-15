"""Analyzer routes: POST /api/v1/ocr, /api/v1/upload, /api/v1/analyze.

Moved verbatim from main.py (v1.8.2 C1c). No ``prefix`` on the APIRouter —
paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from loguru import logger

from app.core.config import settings
from app.core.runtime import (
    _enforce_max_upload_size,
    _resolve_kie_query_fields_in_options,
    call_maybe_async,
    ocr_service,
    process_document,
    tasks,
)
from app.models.api_models import TaskStatus
from app.services.kie.kie_pages import validate_kie_pages_for_non_pdf

router = APIRouter()


@router.post("/api/v1/ocr")
async def ocr_recognize(
    file: UploadFile = File(...),
    language: str = Form("en"),
    engine: Optional[str] = Form(None)
):
    """Simple OCR endpoint for quick text extraction"""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Save file temporarily
    task_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.UPLOAD_DIR, task_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        _enforce_max_upload_size(content, file.filename or "")
        f.write(content)

    try:
        ocr_result = await call_maybe_async(
            ocr_service.recognize,
            file_path,
            language=language,
            engine=engine,
            fallback=True
        )

        return {
            "text": ocr_result.get("full_text", ""),
            "text_blocks": ocr_result.get("text_blocks", []),
            "confidence": ocr_result.get("confidence", 0.0),
            "engine": ocr_result.get("engine_used", "unknown"),
            "page_count": ocr_result.get("page_count", 0),
            "processing_time": ocr_result.get("processing_time", 0)
        }
    except Exception as e:
        logger.error(f"OCR error: {e}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
    finally:
        # Cleanup
        try:
            if os.path.exists(upload_dir):
                shutil.rmtree(upload_dir)
        except:
            pass


@router.post("/api/v1/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file and return task_id for preview purposes.
    This endpoint only uploads the file without processing, allowing immediate preview.
    """
    # Validate file
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Create task_id and save file
    task_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.UPLOAD_DIR, task_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        _enforce_max_upload_size(content, file.filename or "")
        f.write(content)

    # Create minimal task entry for preview purposes
    task = {
        "task_id": task_id,
        "status": "uploaded",
        "progress": 0,
        "message": "File uploaded, ready for preview",
        "created_at": datetime.now(),
        "completed_at": None,
        "file_path": file_path,
        "file_name": file.filename,
        "options": {},
        "result": None
    }
    tasks[task_id] = task

    page_count = 1
    if ext == ".pdf":
        try:
            from app.services.pdf_raster import pdf_page_count

            page_count = max(1, pdf_page_count(file_path))
        except Exception:
            page_count = 1

    return {
        "task_id": task_id,
        "file_name": file.filename,
        "status": "uploaded",
        "message": "File uploaded successfully",
        "page_count": page_count,
    }


@router.post("/api/v1/analyze", response_model=TaskStatus)
async def analyze_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    enable_layout: bool = Form(True),
    enable_table: bool = Form(True),
    enable_formula: bool = Form(False),
    enable_seal: bool = Form(False),
    enable_figure_export: bool = Form(True),
    enable_kie: bool = Form(False),
    document_type: str = Form("auto"),
    language: str = Form("en"),
    ocr_engine: Optional[str] = Form(None),
    layout_engine: Optional[str] = Form(None),
    table_engine: Optional[str] = Form(None),
    table_allow_fullpage_fallback: Optional[bool] = Form(None),
    formula_disable_layout: bool = Form(False),
    formula_disable_preprocess: bool = Form(False),
    formula_two_stage_threshold_retry: bool = Form(True),
    formula_primary_layout_threshold: float = Form(0.5),
    formula_fallback_layout_threshold: float = Form(0.2),
    formula_layout_threshold: Optional[float] = Form(None),
    pipeline_formula_batch_size: int = Form(1),
    return_raw: bool = Form(False),
    kie_query_fields: Optional[str] = Form(None),
    kie_pages: Optional[str] = Form(None),
    table_template: Optional[str] = Form(None),
    enable_hitl: bool = Form(True),
    table_text_backfill: str = Form("auto"),
):
    """Upload and analyze a single document"""
    # Validate file
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    is_pdf = ext == ".pdf"
    pages_err = validate_kie_pages_for_non_pdf(kie_pages, is_pdf, enable_kie=enable_kie)
    if pages_err:
        raise HTTPException(status_code=400, detail=pages_err)

    # CRITICAL FIX: FastAPI parses "1"/"0" as True/False for bool Form fields
    # "true"/"false" strings will cause validation errors
    logger.info(
        "Analyze endpoint received - enable_layout={}, enable_table={}, "
        "enable_formula={}, enable_seal={}, enable_kie={}, document_type={}, "
        "table_allow_fullpage_fallback={}, formula_disable_layout={}, formula_disable_preprocess={}, "
        "pipeline_formula_batch_size={}, return_raw={}",
        enable_layout,
        enable_table,
        enable_formula,
        enable_seal,
        enable_kie,
        document_type,
        table_allow_fullpage_fallback,
        formula_disable_layout,
        formula_disable_preprocess,
        pipeline_formula_batch_size,
        return_raw,
    )

    task_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.UPLOAD_DIR, task_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        _enforce_max_upload_size(content, file.filename or "")
        f.write(content)

    from app.models.analyze_options import AnalyzeOptions, options_to_pipeline_dict

    analyze_options = AnalyzeOptions(
        enable_layout=enable_layout,
        enable_table=enable_table,
        enable_formula=enable_formula,
        enable_seal=enable_seal,
        enable_figure_export=enable_figure_export,
        enable_kie=enable_kie,
        document_type=document_type,
        language=language,
        ocr_engine=ocr_engine,
        layout_engine=layout_engine,
        table_engine=table_engine,
        table_allow_fullpage_fallback=table_allow_fullpage_fallback,
        formula_disable_layout=formula_disable_layout,
        formula_disable_preprocess=formula_disable_preprocess,
        formula_two_stage_threshold_retry=formula_two_stage_threshold_retry,
        formula_primary_layout_threshold=formula_primary_layout_threshold,
        formula_fallback_layout_threshold=formula_fallback_layout_threshold,
        formula_layout_threshold=formula_layout_threshold,
        pipeline_formula_batch_size=pipeline_formula_batch_size,
        return_raw=return_raw,
        kie_query_fields=kie_query_fields,
        kie_pages=kie_pages,
        table_template=table_template,
        enable_hitl=enable_hitl,
        table_text_backfill=table_text_backfill,
    )
    options = options_to_pipeline_dict(
        analyze_options,
        table_allow_fullpage_fallback_default=settings.TABLE_ALLOW_FULLPAGE_FALLBACK,
        table_text_backfill_kill_switch=settings.TABLE_TEXT_BACKFILL,
    )

    _resolve_kie_query_fields_in_options(options)

    # Backward-compatible fallback: if user selected a document_type that typically
    # requires KIE (invoice/receipt/id_card) but did not explicitly enable KIE,
    # enable it automatically as a short-term safety net.
    try:
        doc_type_norm = str(document_type or "").strip().lower()
        if doc_type_norm in {"invoice", "receipt", "id_card"} and not options.get("enable_kie", False):
            options["enable_kie"] = True
            logger.info(f"Analyze endpoint compatibility: auto-enabled KIE for document_type={doc_type_norm}")
    except Exception:
        pass

    # Explicitly log the final analyze options so server-side observers
    # (cloud testing / CI logs) can verify whether KIE was enabled without
    # inspecting the browser request payload.
    try:
        logger.info("Analyze options: %s", options)
    except Exception:
        # Logging should never break the request flow
        logger.debug("Failed to log analyze options")

    task = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "Task created",
        "created_at": datetime.now(),
        "completed_at": None,
        "file_path": file_path,
        "file_name": file.filename,
        "options": options,
        "result": None
    }
    tasks[task_id] = task

    # WebSocket connections will be created when client connects
    # No need to pre-create anything

    background_tasks.add_task(process_document, task_id)

    return TaskStatus(**task)
