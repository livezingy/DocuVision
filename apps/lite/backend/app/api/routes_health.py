"""Lite API — health and engine discovery routes."""

from __future__ import annotations

import importlib.util
import shutil
from importlib import metadata as importlib_metadata
from typing import Dict

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.lite_result import (
    LITE_API_VERSION,
    LiteEngineAvailability,
    LiteEngineInfo,
    LiteEnginesResponse,
    LiteHealthResponse,
    LiteLimits,
)

router = APIRouter(tags=["health"])


def _package_version(dist_names: list[str]) -> str | None:
    for name in dist_names:
        try:
            return importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            continue
    return None


def _is_importable(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def probe_engine_availability() -> Dict[str, LiteEngineAvailability]:
    pdfplumber_version = _package_version(["pdfplumber"])
    camelot_version = _package_version(["camelot-py", "camelot"])
    easyocr_version = _package_version(["easyocr"])
    transformer_version = _package_version(["transformers"])

    tesseract_available = shutil.which("tesseract") is not None

    engines: Dict[str, LiteEngineAvailability] = {
        "pdfplumber": LiteEngineAvailability(
            available=pdfplumber_version is not None,
            version=pdfplumber_version,
            reason=None if pdfplumber_version else "not installed",
        ),
        "camelot": LiteEngineAvailability(
            available=camelot_version is not None,
            version=camelot_version,
            reason=None if camelot_version else "not installed",
        ),
        "tesseract": LiteEngineAvailability(
            available=tesseract_available,
            version=None,
            reason=None if tesseract_available else "binary not found",
        ),
        "easyocr": LiteEngineAvailability(
            available=easyocr_version is not None,
            version=easyocr_version,
            reason=None if easyocr_version else "not installed",
        ),
        "transformer": LiteEngineAvailability(
            available=transformer_version is not None and _is_importable("torch"),
            version=transformer_version,
            reason=None
            if transformer_version and _is_importable("torch")
            else "heavy profile not installed",
        ),
    }
    return engines


def build_engine_catalog() -> LiteEnginesResponse:
    return LiteEnginesResponse(
        engines=[
            LiteEngineInfo(
                id="pdfplumber",
                label="PDFPlumber",
                file_types=["pdf_digital"],
                description="Best for digital PDFs and borderless tables.",
                profile="cpu",
                flavors=["auto", "lines", "text"],
            ),
            LiteEngineInfo(
                id="camelot",
                label="Camelot",
                file_types=["pdf_digital"],
                description="Best for bordered tables in digital PDFs.",
                profile="cpu",
                flavors=["auto", "lattice", "stream"],
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
