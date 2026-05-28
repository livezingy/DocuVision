"""Unit tests for Lite OCR pipeline (EasyOCR bbox mapping)."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.ocr_pipeline import (
    TEXT_PREVIEW_MAX_BLOCKS,
    TEXT_PREVIEW_MAX_CHARS,
    _normalize_easyocr_bbox,
    _run_easyocr,
    _run_tesseract,
    build_text_preview,
    extract_ocr_from_image,
)

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


def test_run_tesseract_groups_words_into_paragraphs():
    import sys
    from unittest.mock import MagicMock

    mock_pytesseract = MagicMock()
    mock_pytesseract.Output = MagicMock()
    mock_pytesseract.Output.DICT = "dict"
    mock_pytesseract.image_to_data.return_value = {
        "level": [5, 5, 5, 5],
        "text": ["Hello", "world.", "Second", "paragraph"],
        "conf": [90, 88, 92, 91],
        "page_num": [1, 1, 1, 1],
        "block_num": [1, 1, 2, 2],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 1, 1],
        "left": [10, 60, 10, 80],
        "top": [20, 20, 50, 50],
        "width": [40, 40, 50, 60],
        "height": [12, 12, 12, 12],
    }

    image = Image.new("RGB", (200, 100), "white")
    with patch.dict(sys.modules, {"pytesseract": mock_pytesseract}):
        blocks = _run_tesseract(image, min_confidence=0.5)

    assert len(blocks) == 2
    assert blocks[0]["text"] == "Hello world."
    assert blocks[1]["text"] == "Second paragraph"
    assert blocks[0]["engine"] == "tesseract"


def test_text_preview_truncates_but_ocr_full():
    blocks = [{"text": f"word{i}", "confidence": 0.9} for i in range(30)]
    preview = build_text_preview(blocks)
    assert preview is not None
    assert len(preview) <= TEXT_PREVIEW_MAX_CHARS
    assert len(blocks) == 30
    full_join = " ".join(b["text"] for b in blocks)
    assert len(full_join) > len(preview)


@patch("app.services.ocr_pipeline._resolve_ocr_engine", return_value="easyocr")
@patch("app.services.ocr_pipeline._run_easyocr")
def test_extract_ocr_returns_full_blocks_and_truncated_preview(mock_run_easyocr, _mock_resolve):
    mock_run_easyocr.return_value = [
        {
            "page": 1,
            "bbox": [0.0, 0.0, 10.0, 10.0],
            "text": f"block{i}",
            "confidence": 0.9,
            "engine": "easyocr",
        }
        for i in range(TEXT_PREVIEW_MAX_BLOCKS + 5)
    ]
    buf = BytesIO()
    Image.new("RGB", (10, 10), "white").save(buf, format="PNG")
    buf.seek(0)
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(buf.getvalue())
        tmp_path = Path(tmp.name)

    try:
        output = extract_ocr_from_image(tmp_path, mode="smart", engine="auto")
        assert len(output["ocr"]) == TEXT_PREVIEW_MAX_BLOCKS + 5
        assert output["text_preview"] is not None
        assert len(output["text_preview"]) <= TEXT_PREVIEW_MAX_CHARS
    finally:
        tmp_path.unlink(missing_ok=True)


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
