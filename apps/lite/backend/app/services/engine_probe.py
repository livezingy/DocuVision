"""Engine availability probing for Lite."""

from __future__ import annotations

import importlib.util
import shutil
from importlib import metadata as importlib_metadata
from typing import Dict

from app.schemas.lite_result import LiteEngineAvailability


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
            available=transformer_version is not None and _is_importable("torch"),
            version=transformer_version,
            reason=None
            if transformer_version and _is_importable("torch")
            else "heavy profile not installed",
        ),
    }
