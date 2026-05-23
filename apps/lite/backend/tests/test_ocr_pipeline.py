"""Unit tests for Lite OCR pipeline (EasyOCR bbox mapping)."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.ocr_pipeline import _normalize_easyocr_bbox, _run_easyocr

client = TestClient(app)


def test_normalize_easyocr_bbox_from_bbox_rect():
    block = {"bbox_rect": [10, 20, 110, 80], "bbox": [[0, 0], [100, 0], [100, 60], [0, 60]]}
    assert _normalize_easyocr_bbox(block) == [10.0, 20.0, 110.0, 80.0]


def test_normalize_easyocr_bbox_from_corner_points():
    block = {
        "bbox": [[0, 0], [100, 0], [100, 60], [0, 60]],
    }
    assert _normalize_easyocr_bbox(block) == [0.0, 0.0, 100.0, 60.0]


def test_normalize_easyocr_bbox_empty():
    assert _normalize_easyocr_bbox({}) == []


@patch("app.services.ocr_pipeline._create_easyocr_engine")
def test_run_easyocr_maps_bbox_rect(mock_create_engine):
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_engine.recognize_text.return_value = [
        {
            "text": "Hello",
            "bbox": [[1, 2], [3, 2], [3, 4], [1, 4]],
            "bbox_rect": [1.0, 2.0, 3.0, 4.0],
            "confidence": 0.91,
        }
    ]

    image = Image.new("RGB", (20, 20), "white")
    blocks = _run_easyocr(image, ["en"], min_confidence=0.5)

    assert len(blocks) == 1
    assert blocks[0]["bbox"] == [1.0, 2.0, 3.0, 4.0]
    assert blocks[0]["text"] == "Hello"
    assert blocks[0]["engine"] == "easyocr"
    assert blocks[0]["confidence"] == pytest.approx(0.91)


@patch("app.services.ocr_pipeline._run_easyocr")
def test_extract_auto_image_easyocr(mock_run_easyocr):
    mock_run_easyocr.return_value = [
        {
            "page": 1,
            "bbox": [0.0, 0.0, 50.0, 20.0],
            "text": "Table",
            "confidence": 0.88,
            "engine": "easyocr",
        }
    ]

    buf = BytesIO()
    Image.new("RGB", (50, 20), "white").save(buf, format="PNG")
    buf.seek(0)

    response = client.post(
        "/api/v1/lite/extract/auto",
        files={"file": ("table.png", buf, "image/png")},
        data={"mode": "smart"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["input"]["detected_file_type"] == "image"
    assert data["routing"]["engine_used"] == "easyocr"
    assert data["ocr"] is not None
    assert len(data["ocr"]) == 1
    assert data["ocr"][0]["bbox"] == [0.0, 0.0, 50.0, 20.0]
    assert data["ocr"][0]["text"] == "Table"
