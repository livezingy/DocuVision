"""Lite analyze routes — document profile pre-scan."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.upload_utils import validate_upload
from app.schemas.lite_result import LiteDocumentProfile, LiteError, LiteErrorResponse
from app.services.profile_pipeline import build_document_profile

router = APIRouter(tags=["analyze"])


@router.post("/analyze/profile", response_model=LiteDocumentProfile)
async def analyze_profile(file: UploadFile = File(...)) -> LiteDocumentProfile:
    raw = await file.read()
    validate_upload(file, raw)

    suffix = Path(file.filename or "upload.bin").suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)

    try:
        return build_document_profile(tmp_path, mime_type=file.content_type or "")
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=LiteErrorResponse(
                error=LiteError(code="unsupported_file_type", message=str(exc))
            ).model_dump(),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=LiteErrorResponse(
                error=LiteError(code="internal_error", message=str(exc))
            ).model_dump(),
        ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
