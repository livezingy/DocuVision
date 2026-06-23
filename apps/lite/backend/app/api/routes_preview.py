"""Lite preview routes — upload for immediate PDF/image preview without full extraction."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.api.upload_utils import validate_upload
from app.schemas.lite_result import LiteError, LiteErrorResponse, LitePreviewResponse
from app.services.file_detector import IMAGE_EXTENSIONS
from app.services.preview_renderer import render_page_png
from app.services.preview_store import preview_store

router = APIRouter(tags=["preview"])

_ALLOWED_SUFFIXES = {".pdf", *IMAGE_EXTENSIONS}


@router.post("/preview", response_model=LitePreviewResponse)
async def create_preview(file: UploadFile = File(...)) -> LitePreviewResponse:
    raw = await file.read()
    validate_upload(file, raw)

    suffix = Path(file.filename or "upload.bin").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=LiteErrorResponse(
                error=LiteError(
                    code="unsupported_file_type",
                    message=f"Preview supports PDF and images only (got {suffix or 'unknown'})",
                )
            ).model_dump(),
        )

    safe_name = Path(file.filename or f"upload{suffix}").name
    preview_id, page_count = preview_store.create_from_upload(safe_name, raw)

    return LitePreviewResponse(
        preview_id=preview_id,
        page_count=page_count,
        file_name=safe_name,
    )


@router.get("/preview/{preview_id}/page-image/{page_num}")
async def get_preview_page_image(preview_id: str, page_num: int) -> Response:
    session = preview_store.get(preview_id)
    if not session:
        raise HTTPException(status_code=404, detail="Preview session not found")

    file_path = Path(session["file_path"])
    if not file_path.exists():
        preview_store.delete(preview_id)
        raise HTTPException(status_code=404, detail="Preview file not found")

    max_page = int(session.get("page_count") or 1)
    if page_num < 1 or page_num > max_page:
        raise HTTPException(
            status_code=400,
            detail=f"Page number {page_num} out of range (1-{max_page})",
        )

    png_bytes = render_page_png(file_path, page_num)
    media_type = "image/png" if file_path.suffix.lower() == ".pdf" else _guess_image_media_type(file_path)
    return Response(
        content=png_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename=page_{page_num}.png"},
    )


def _guess_image_media_type(file_path: Path) -> str:
    ext = file_path.suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    return f"image/{ext or 'png'}"
