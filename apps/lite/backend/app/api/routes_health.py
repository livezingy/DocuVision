"""Lite API — health and engine discovery routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.lite_result import (
    LITE_API_VERSION,
    LiteEngineInfo,
    LiteEnginesResponse,
    LiteHealthResponse,
    LiteLimits,
)
from app.services.engine_probe import probe_engine_availability

router = APIRouter(tags=["health"])


def build_engine_catalog() -> LiteEnginesResponse:
    return LiteEnginesResponse(
        engines=[
            LiteEngineInfo(
                id="pdfplumber",
                label="PDFPlumber",
                file_types=["pdf_digital"],
                description="Digital PDF tables; bordered uses line detection, unbordered uses text alignment.",
                profile="cpu",
                flavors=["auto", "bordered", "unbordered"],
            ),
            LiteEngineInfo(
                id="camelot",
                label="Camelot",
                file_types=["pdf_digital"],
                description="Digital PDF tables; bordered uses lattice mode, unbordered uses stream mode.",
                profile="cpu",
                flavors=["auto", "bordered", "unbordered"],
            ),
            LiteEngineInfo(
                id="tesseract",
                label="Tesseract",
                file_types=["image", "pdf_scan"],
                description="Lightweight OCR for simple scans.",
                profile="cpu",
            ),
            LiteEngineInfo(
                id="easyocr",
                label="EasyOCR",
                file_types=["image", "pdf_scan"],
                description="CPU OCR for scans; better for mixed CN/EN.",
                profile="cpu",
            ),
            LiteEngineInfo(
                id="transformer",
                label="Transformer",
                file_types=["image"],
                description="High-accuracy table detection; requires local/heavy profile.",
                profile="heavy",
            ),
        ]
    )


@router.get("/health", response_model=LiteHealthResponse)
def get_health() -> LiteHealthResponse:
    return LiteHealthResponse(
        status="ok",
        service="docuvision-lite",
        api_version=LITE_API_VERSION,
        profile="cpu",
        engines=probe_engine_availability(),
        limits=LiteLimits(
            max_file_size_mb=settings.MAX_FILE_SIZE_MB,
            max_pages=settings.MAX_PAGES,
            sync_max_pages=settings.SYNC_MAX_PAGES,
        ),
    )


@router.get("/engines", response_model=LiteEnginesResponse)
def get_engines() -> LiteEnginesResponse:
    return build_engine_catalog()
