"""Shared upload validation for Lite routes."""

from __future__ import annotations

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.schemas.lite_result import LiteError, LiteErrorResponse


def validate_upload(file: UploadFile, raw: bytes) -> None:
    size_mb = len(raw) / (1024 * 1024)
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=LiteErrorResponse(
                error=LiteError(
                    code="file_too_large",
                    message=f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB} MB",
                    details={
                        "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
                        "actual_size_mb": round(size_mb, 2),
                    },
                )
            ).model_dump(),
        )
