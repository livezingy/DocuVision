"""Lite extract routes."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.api.upload_utils import validate_upload
from app.core.config import settings
from app.core.feature_flags import raster_table_extraction_enabled
from app.schemas.lite_result import (
    ExtractMode,
    JobStatus,
    LiteError,
    LiteErrorResponse,
    LiteJobAccepted,
    LiteResult,
    WarningCode,
)
from app.services.file_detector import detect_file_type
from app.services.image_table_pipeline import extract_tables_from_image
from app.services.job_store import job_store
from app.services.lite_builder import build_lite_result, timed_pipeline
from app.services.ocr_pipeline import extract_ocr_from_image
from app.services.pipeline_merge import _empty_scan_image_result, merge_pipeline_outputs
from app.services.table_pipeline import extract_digital_pdf_text, extract_tables_from_pdf

router = APIRouter(tags=["extract"])

_RASTER_TABLE_FROZEN_MESSAGE = (
    "Raster table extraction (Transformer) is disabled in Lite; text OCR only."
)


def _run_pipeline(
    file_path: Path,
    mime_type: str,
    mode: ExtractMode,
    engine: str,
    flavor: str,
    pages: Optional[str],
    score_threshold: float,
    param_mode: str = "auto",
    custom_params: Optional[str] = None,
    ocr_engine: str = "auto",
    languages: Optional[str] = None,
    extract_tables: bool = True,
    extract_text: bool = True,
    use_transformer: bool = True,
    table_areas: Optional[str] = None,
    table_template: Optional[str] = None,
):
    detected, page_count = detect_file_type(file_path, mime_type)
    lang_list = [p.strip() for p in (languages or "eng").split(",") if p.strip()] or ["eng"]

    if detected.value == "pdf_digital":
        if extract_tables:
            output = extract_tables_from_pdf(
                file_path,
                mode=mode,
                engine=engine,
                flavor=flavor,
                pages_spec=pages,
                score_threshold=score_threshold,
                param_mode=param_mode,
                custom_params=custom_params,
                max_pages=settings.MAX_PAGES,
                table_areas=table_areas,
                table_template=table_template,
            )
            output["detected_file_type"] = detected
            output["page_count"] = page_count
            return output
        if extract_text:
            output = extract_digital_pdf_text(
                file_path,
                pages_spec=pages,
                max_pages=settings.MAX_PAGES,
            )
            output["detected_file_type"] = detected
            output["page_count"] = page_count
            return output
        return {
            "tables": [],
            "ocr": [],
            "text_preview": None,
            "routing": {"engine_used": "none", "mode": mode.value if hasattr(mode, "value") else mode},
            "quality": {"overall_confidence": 0.0, "tables_found": 0, "tables_accepted": 0},
            "warnings": [],
            "detected_file_type": detected,
            "page_count": page_count,
        }

    if detected.value in {"pdf_scan", "image"}:
        if not extract_tables and not extract_text:
            return _empty_scan_image_result(detected, page_count)

        result = _empty_scan_image_result(detected, page_count)
        result["routing"] = {"mode": mode.value if hasattr(mode, "value") else mode}

        raster_tables_requested = (
            extract_tables
            and detected.value in {"image", "pdf_scan"}
            and use_transformer
        )
        if raster_tables_requested and not raster_table_extraction_enabled():
            result["warnings"].append(
                {
                    "code": WarningCode.RASTER_TABLE_FROZEN.value,
                    "message": _RASTER_TABLE_FROZEN_MESSAGE,
                }
            )
        elif raster_tables_requested and raster_table_extraction_enabled():
            try:
                table_ocr_engine = None
                if mode == ExtractMode.ADVANCED and ocr_engine not in ("auto", ""):
                    table_ocr_engine = ocr_engine
                table_output = extract_tables_from_image(
                    file_path,
                    mode=mode,
                    score_threshold=score_threshold,
                    pages_spec=pages,
                    max_pages=settings.MAX_PAGES,
                    table_ocr_engine=table_ocr_engine,
                    table_ocr_languages=lang_list,
                )
                result = merge_pipeline_outputs(result, table_output)
            except RuntimeError as exc:
                result["warnings"].append(
                    {
                        "code": WarningCode.TRANSFORMER_UNAVAILABLE.value,
                        "message": str(exc),
                    }
                )

        if extract_text:
            ocr_output = extract_ocr_from_image(
                file_path,
                mode=mode,
                engine=ocr_engine if mode == ExtractMode.ADVANCED else engine,
                languages=lang_list,
                max_pages=settings.MAX_PAGES,
                pages_spec=pages,
            )
            result = merge_pipeline_outputs(result, ocr_output)

        return result
    raise ValueError("Unsupported file type for Lite extraction")


@router.post("/extract/tables", response_model=LiteResult)
async def extract_tables(
    file: UploadFile = File(...),
    mode: ExtractMode = Form(ExtractMode.SMART),
    engine: str = Form("auto"),
    flavor: str = Form("auto"),
    pages: Optional[str] = Form(None),
    score_threshold: float = Form(0.5),
    param_mode: str = Form("auto"),
    custom_params: Optional[str] = Form(None),
):
    raw = await file.read()
    validate_upload(file, raw)
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
            param_mode=param_mode,
            custom_params=custom_params,
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
    validate_upload(file, raw)
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
    param_mode: str = Form("auto"),
    custom_params: Optional[str] = Form(None),
    ocr_engine: str = Form("auto"),
    languages: Optional[str] = Form(None),
    extract_tables: bool = Form(True),
    extract_text: bool = Form(True),
    use_transformer: bool = Form(True),
    table_areas: Optional[str] = Form(None),
    table_template: Optional[str] = Form(None),
):
    raw = await file.read()
    validate_upload(file, raw)
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
            param_mode,
            custom_params,
            ocr_engine,
            languages,
            extract_tables,
            extract_text,
            use_transformer,
            table_areas,
            table_template,
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
        extract_tables_raw = form.get("extract_tables", True)
        extract_text_raw = form.get("extract_text", True)
        use_transformer_raw = form.get("use_transformer", True)
        pipeline_output, elapsed = timed_pipeline(
            _run_pipeline,
            upload_path,
            mime_type,
            ExtractMode(form.get("mode", "smart")),
            form.get("engine", "auto"),
            form.get("flavor", "auto"),
            form.get("pages"),
            float(form.get("score_threshold", 0.5)),
            form.get("param_mode", "auto"),
            form.get("custom_params"),
            form.get("ocr_engine", "auto"),
            form.get("languages"),
            extract_tables_raw if isinstance(extract_tables_raw, bool) else str(extract_tables_raw).lower() == "true",
            extract_text_raw if isinstance(extract_text_raw, bool) else str(extract_text_raw).lower() == "true",
            use_transformer_raw if isinstance(use_transformer_raw, bool) else str(use_transformer_raw).lower() == "true",
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
    param_mode: str = Form("auto"),
    custom_params: Optional[str] = Form(None),
    ocr_engine: str = Form("auto"),
    languages: Optional[str] = Form(None),
    extract_tables: bool = Form(True),
    extract_text: bool = Form(True),
    use_transformer: bool = Form(True),
):
    raw = await file.read()
    validate_upload(file, raw)
    job_id = job_store.create()
    upload_path = job_store.save_upload(job_id, file.filename or "upload.bin", raw)
    form = {
        "mode": mode.value if hasattr(mode, "value") else mode,
        "engine": engine,
        "flavor": flavor,
        "pages": pages,
        "score_threshold": score_threshold,
        "param_mode": param_mode,
        "custom_params": custom_params,
        "ocr_engine": ocr_engine,
        "languages": languages,
        "extract_tables": extract_tables,
        "extract_text": extract_text,
        "use_transformer": use_transformer,
    }
    background_tasks.add_task(_background_extract, job_id, upload_path, file.content_type or "", form)
    return LiteJobAccepted(
        job_id=job_id,
        status=JobStatus.PENDING,
        poll_url=f"/api/v1/lite/jobs/{job_id}",
        result_url=f"/api/v1/lite/jobs/{job_id}/result",
    )
