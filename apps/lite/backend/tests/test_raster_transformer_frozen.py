"""Integration tests: raster Transformer table extraction frozen in Lite."""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buf, format="PNG")
    return buf.getvalue()


@patch("app.services.ocr_pipeline._run_easyocr")
@patch("app.api.routes_extract.extract_tables_from_image")
def test_extract_auto_raster_skips_transformer_and_emits_warning(mock_extract_tables, mock_run_easyocr):
    mock_run_easyocr.return_value = [
        {
            "page": 1,
            "bbox": [0, 0, 10, 10],
            "text": "hello",
            "confidence": 0.9,
            "engine": "easyocr",
        }
    ]

    response = client.post(
        "/api/v1/lite/extract/auto",
        files={"file": ("scan.png", _png_bytes(), "image/png")},
        data={
            "mode": "smart",
            "extract_tables": "true",
            "extract_text": "true",
            "use_transformer": "true",
        },
    )

    assert response.status_code == 200, response.text
    mock_extract_tables.assert_not_called()

    data = response.json()
    warning_codes = {w.get("code") for w in data.get("warnings", [])}
    assert "raster_table_frozen" in warning_codes
    assert data["routing"]["engine_used"] == "easyocr"
