"""Lite extract routes."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.schemas.lite_result import (
    ExtractMode,
    JobStatus,
    LiteError,
    LiteErrorResponse,
    LiteJobAccepted,
    LiteResult,
)
from app.services.file_detector import detect_file_type
from app.services.job_store import job_store
from app.services.lite_builder import build_lite_result, timed_pipeline
from app.services.ocr_pipeline import extract_ocr_from_image
from app.services.table_pipeline import extract_tables_from_pdf

router = APIRouter(tags=["extract"])


def _validate_upload(file: UploadFile, raw: bytes) -> None:
    size_mb = len(raw) / (1024 * 1024)
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=LiteErrorResponse(
                error=LiteError(
                    code="file_too_large",
                    message=f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB} MB",
                    details={"max_file_size_mb": settings.MAX_FILE_SIZE_MB, "actual_size_mb": round(size_mb, 2)},
                )
            ).model_dump(),
        )


def _run_pipeline(file_path: Path, mime_type: str, mode: ExtractMode, engine: str, flavor: str, pages: Optional[str], score_threshold: float):
    detected, page_count = detect_file_type(file_path, mime_type)
    if detected.value == "pdf_digital":
        output = extract_tables_from_pdf(
            file_path,
            mode=mode,
            engine=engine,
            flavor=flavor,
            pages_spec=pages,
            score_threshold=score_threshold,
            max_pages=settings.MAX_PAGES,
        )
        output["detected_file_type"] = detected
        output["page_count"] = page_count
        return output
    if detected.value in {"pdf_scan", "image"}:
        output = extract_ocr_from_image(file_path, mode=mode, engine=engine)
        output["detected_file_type"] = detected
        output["page_count"] = page_count
        return output
    raise ValueError("Unsupported file type for Lite extraction")


@router.post("/extract/tables", response_model=LiteResult)
async def extract_tables(
    file: UploadFile = File(...),
    mode: ExtractMode = Form(ExtractMode.SMART),
    engine: str = Form("auto"),
    flavor: str = Form("auto"),
    pages: Optional[str] = Form(None),
    score_threshold: float = Form(0.5),
):
    raw = await file.read()
    _validate_upload(file, raw)
    job_id = job_store.create()
    upload_path = job_store.save_upload(job_id, file.filename or "upload.pdf", raw)
    try:
        pipeline_output, elapsed = timed_pipeline(
            extract_tables_from_pdf,
            upload_path,
            mode=mode,
            engine=engine,
            flavor=flavor,
            pages_spec=pages,
            score_threshold=score_threshold,
            max_pages=settings.MAX_PAGES,
        )
        result = build_lite_result(
            job_id=job_id,
            file_path=upload_path,
            mime_type=file.content_type or "",
            pipeline_output=pipeline_output,
            processing_ms=elapsed,
        )
        job_store.save_result(job_id, result.model_dump(mode="json"))
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=LiteErrorResponse(error=LiteError(code="validation_error", message=str(exc))).model_dump(),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=LiteErrorResponse(
                error=LiteError(code="engine_runtime_error", message=str(exc))
            ).model_dump(),
        ) from exc


@router.post("/extract/ocr", response_model=LiteResult)
async def extract_ocr(
    file: UploadFile = File(...),
    mode: ExtractMode = Form(ExtractMode.SMART),
    engine: str = Form("auto"),
    min_confidence: float = Form(0.5),
):
    raw = await file.read()
    _validate_upload(file, raw)
    job_id = job_store.create()
    upload_path = job_store.save_upload(job_id, file.filename or "upload.png", raw)
    try:
        pipeline_output, elapsed = timed_pipeline(
            extract_ocr_from_image,
            upload_path,
            mode=mode,
            engine=engine,
            min_confidence=min_confidence,
        )
        detected, page_count = detect_file_type(upload_path, file.content_type)
        pipeline_output["detected_file_type"] = detected
        pipeline_output["page_count"] = page_count
        result = build_lite_result(
            job_id=job_id,
            file_path=upload_path,
            mime_type=file.content_type or "",
            pipeline_output=pipeline_output,
            processing_ms=elapsed,
        )
        job_store.save_result(job_id, result.model_dump(mode="json"))
        return result
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=LiteErrorResponse(error=LiteError(code="engine_unavailable", message=str(exc))).model_dump(),
        ) from exc


@router.post("/extract/auto", response_model=LiteResult)
async def extract_auto(
    file: UploadFile = File(...),
    mode: ExtractMode = Form(ExtractMode.SMART),
    engine: str = Form("auto"),
    flavor: str = Form("auto"),
    pages: Optional[str] = Form(None),
    score_threshold: float = Form(0.5),
):
    raw = await file.read()
    _validate_upload(file, raw)
    job_id = job_store.create()
    upload_path = job_store.save_upload(job_id, file.filename or "upload.bin", raw)
    try:
        pipeline_output, elapsed = timed_pipeline(
            _run_pipeline,
            upload_path,
            file.content_type or "",
            mode,
            engine,
            flavor,
            pages,
            score_threshold,
        )
        result = build_lite_result(
            job_id=job_id,
            file_path=upload_path,
            mime_type=file.content_type or "",
            pipeline_output=pipeline_output,
            processing_ms=elapsed,
        )
        job_store.save_result(job_id, result.model_dump(mode="json"))
        return result
    except ValueError as exc:
        code = "unsupported_file_type" if "Unsupported file" in str(exc) else "validation_error"
        status = 400
        raise HTTPException(
            status_code=status,
            detail=LiteErrorResponse(error=LiteError(code=code, message=str(exc))).model_dump(),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=LiteErrorResponse(
                error=LiteError(code="engine_runtime_error", message=str(exc))
            ).model_dump(),
        ) from exc


def _background_extract(job_id: str, upload_path: Path, mime_type: str, form: dict) -> None:
    job_store.update(job_id, status=JobStatus.RUNNING.value)
    try:
        pipeline_output, elapsed = timed_pipeline(
            _run_pipeline,
            upload_path,
            mime_type,
            ExtractMode(form.get("mode", "smart")),
            form.get("engine", "auto"),
            form.get("flavor", "auto"),
            form.get("pages"),
            float(form.get("score_threshold", 0.5)),
        )
        result = build_lite_result(
            job_id=job_id,
            file_path=upload_path,
            mime_type=mime_type,
            pipeline_output=pipeline_output,
            processing_ms=elapsed,
        )
        job_store.save_result(job_id, result.model_dump(mode="json"))
    except Exception as exc:
        job_store.update(job_id, status=JobStatus.FAILED.value, error={"message": str(exc)})


@router.post("/jobs", response_model=LiteJobAccepted, status_code=202)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: ExtractMode = Form(ExtractMode.SMART),
    engine: str = Form("auto"),
    flavor: str = Form("auto"),
    pages: Optional[str] = Form(None),
    score_threshold: float = Form(0.5),
):
    raw = await file.read()
    _validate_upload(file, raw)
    job_id = job_store.create()
    upload_path = job_store.save_upload(job_id, file.filename or "upload.bin", raw)
    form = {
        "mode": mode.value if hasattr(mode, "value") else mode,
        "engine": engine,
        "flavor": flavor,
        "pages": pages,
        "score_threshold": score_threshold,
    }
    background_tasks.add_task(_background_extract, job_id, upload_path, file.content_type or "", form)
    return LiteJobAccepted(
        job_id=job_id,
        status=JobStatus.PENDING,
        poll_url=f"/api/v1/lite/jobs/{job_id}",
        result_url=f"/api/v1/lite/jobs/{job_id}/result",
    )
