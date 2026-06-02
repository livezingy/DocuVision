"""Engine availability probing for Lite."""

from __future__ import annotations

import importlib.util
import shutil
from importlib import metadata as importlib_metadata
from typing import Dict

from app.schemas.lite_result import LiteEngineAvailability
from app.core.feature_flags import raster_table_extraction_enabled


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
    transformer_installed = transformer_version is not None and _is_importable("torch")
    transformer_available = transformer_installed and raster_table_extraction_enabled()

    tesseract_available = shutil.which("tesseract") is not None

    return {
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
            available=transformer_available,
            version=transformer_version,
            reason=None
            if transformer_available
            else (
                "disabled in Lite"
                if transformer_installed and not raster_table_extraction_enabled()
                else "heavy profile not installed"
            ),
        ),
    }
