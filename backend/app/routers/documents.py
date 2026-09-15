"""Documents routes: POST /api/v1/documents:analyze, /api/v1/document/profile.

Moved verbatim from main.py (v1.8.2 C1d). No ``prefix`` on the APIRouter —
paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from loguru import logger

from app.core.config import settings
from app.core.runtime import (
    _enforce_max_upload_size,
    _resolve_kie_query_fields_in_options,
    process_document,
    tasks,
)
from app.models.api_models import JobStatus
from app.services.kie.kie_pages import validate_kie_pages_for_non_pdf

router = APIRouter()


@router.post("/api/v1/documents:analyze", response_model=JobStatus)
async def analyze_document_v1(
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
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Phase 1 API: Submit a document for analysis.
    Returns job_id and status. Use /api/v1/jobs/{job_id} to poll status,
    and /api/v1/jobs/{job_id}/result to fetch the Envelope result.

    Request: multipart/form-data with 'file' field
    Response: JobStatus with job_id

    Form parameters mirror POST /api/v1/analyze (legacy) so the Phase 1
    Job-based endpoint is feature-complete (layout/table/formula/seal/KIE
    toggles, engine overrides, formula thresholds, table_template, HITL).
    """
    # Validate file
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    is_pdf = ext == ".pdf"
    pages_err = validate_kie_pages_for_non_pdf(kie_pages, is_pdf, enable_kie=enable_kie)
    if pages_err:
        raise HTTPException(status_code=400, detail=pages_err)

    job_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.UPLOAD_DIR, job_id)
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
    options["use_doc_unwarping"] = settings.USE_DOC_UNWARPING
    options["debug_mode"] = settings.DEBUG_MODE

    _resolve_kie_query_fields_in_options(options)

    # Backward-compatible fallback: if user selected a document_type that
    # typically requires KIE (invoice/receipt/id_card) but did not enable KIE,
    # enable it automatically (mirrors legacy /api/v1/analyze behavior).
    try:
        doc_type_norm = str(document_type or "").strip().lower()
        if doc_type_norm in {"invoice", "receipt", "id_card"} and not options.get("enable_kie", False):
            options["enable_kie"] = True
            logger.info(f"Phase1 analyze: auto-enabled KIE for document_type={doc_type_norm}")
    except Exception:
        pass

    try:
        logger.info("Phase1 analyze options: %s", options)
    except Exception:
        logger.debug("Failed to log phase1 analyze options")

    task = {
        "task_id": job_id,
        "status": "pending",
        "progress": 0,
        "message": "Job created",
        "created_at": datetime.now(),
        "completed_at": None,
        "file_path": file_path,
        "file_name": file.filename,
        "options": options,
        "result": None,
        "envelope": None,  # Will be populated by phase1_envelope_step
    }
    tasks[job_id] = task

    background_tasks.add_task(process_document, job_id)

    return JobStatus(
        job_id=job_id,
        status="running",
        progress=0,
        message="Job created",
        created_at=datetime.now(),
    )


@router.post("/api/v1/document/profile")
async def document_profile_scan(file: UploadFile = File(...)):
    """Pre-scan upload and suggest routing options (Pro Document Profile)."""
    import tempfile

    suffix = os.path.splitext(file.filename or "")[1] or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        from app.services.document_profile import build_document_profile

        return build_document_profile(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
