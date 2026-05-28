"""OCR result messaging: failure vs empty vs low-confidence."""

from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.schemas.lite_result import WarningCode
from app.services.ocr_pipeline import (
    _normalize_easyocr_languages,
    extract_ocr_from_image,
)

# Dummy path: _load_images_from_path is mocked; no real file on disk is required.
_DUMMY_IMAGE = Path("scan.png")


def test_normalize_easyocr_languages_maps_eng_to_en():
    assert _normalize_easyocr_languages(["eng"]) == ["en"]
    assert _normalize_easyocr_languages(["en", "eng"]) == ["en", "en"]


@patch("app.services.ocr_pipeline._load_images_from_path")
@patch("app.services.ocr_pipeline._resolve_ocr_engine", return_value="easyocr")
@patch("app.services.ocr_pipeline._run_easyocr")
def test_low_confidence_still_returns_ocr_blocks(mock_run, _mock_engine, mock_load):
    mock_load.return_value = [(1, Image.new("RGB", (10, 10)))]
    mock_run.return_value = [
        {"page": 1, "bbox": [0, 0, 10, 10], "text": "hello", "confidence": 0.45, "engine": "easyocr"},
    ]

    output = extract_ocr_from_image(_DUMMY_IMAGE, mode="smart", engine="auto")

    assert len(output["ocr"]) == 1
    assert output["ocr"][0]["text"] == "hello"
    codes = {w["code"] for w in output["warnings"]}
    assert WarningCode.LOW_CONFIDENCE.value in codes
    assert WarningCode.NO_TEXT_DETECTED.value not in codes


@patch("app.services.ocr_pipeline._load_images_from_path")
@patch("app.services.ocr_pipeline._resolve_ocr_engine", return_value="easyocr")
@patch("app.services.ocr_pipeline._run_easyocr")
def test_empty_ocr_emits_no_text_detected(mock_run, _mock_engine, mock_load):
    mock_load.return_value = [(1, Image.new("RGB", (10, 10)))]
    mock_run.return_value = []

    output = extract_ocr_from_image(_DUMMY_IMAGE, mode="smart", engine="auto")

    assert output["ocr"] == []
    codes = {w["code"] for w in output["warnings"]}
    assert WarningCode.NO_TEXT_DETECTED.value in codes


@patch("app.services.ocr_pipeline._load_images_from_path")
@patch("app.services.ocr_pipeline._resolve_ocr_engine", return_value="easyocr")
@patch("app.services.ocr_pipeline._run_easyocr", side_effect=RuntimeError("EasyOCR failed to initialize"))
def test_ocr_runtime_error_emits_extraction_failed(mock_run, _mock_engine, mock_load):
    mock_load.return_value = [(1, Image.new("RGB", (10, 10)))]

    output = extract_ocr_from_image(_DUMMY_IMAGE, mode="smart", engine="auto")

    assert output["ocr"] == []
    codes = {w["code"] for w in output["warnings"]}
    assert WarningCode.OCR_EXTRACTION_FAILED.value in codes
