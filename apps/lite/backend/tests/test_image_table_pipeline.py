"""Tests for image Table Transformer pipeline."""

from __future__ import annotations

import asyncio
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PIL import Image

from app.services.image_table_pipeline import extract_tables_from_image


def _write_test_image(path: Path) -> None:
    Image.new("RGB", (32, 32), color="white").save(path)


@pytest.mark.asyncio
async def test_extract_tables_from_image_under_running_loop(tmp_path: Path) -> None:
    """Sync extract must work when called from FastAPI async context (running loop)."""
    img_path = tmp_path / "table.png"
    _write_test_image(img_path)

    mock_result = {
        "success": True,
        "tables": [
            {
                "columns": ["Col"],
                "data": [["val"]],
                "score": 0.95,
                "bbox": [0, 0, 10, 10],
            }
        ],
    }
    detected = SimpleNamespace(value="image")

    async def fake_parser(_image: Image.Image, **kwargs) -> dict:
        return mock_result

    with patch(
        "app.services.image_table_pipeline.raster_table_extraction_enabled",
        return_value=True,
    ), patch(
        "app.services.image_table_pipeline._transformer_available",
        return_value=True,
    ), patch(
        "app.services.image_table_pipeline._run_transformer_parser",
        fake_parser,
    ), patch(
        "app.services.image_table_pipeline.detect_file_type",
        return_value=(detected, 1),
    ):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = extract_tables_from_image(img_path)

    assert len(result["tables"]) == 1
    assert result["tables"][0]["headers"] == ["Col"]
    assert result["routing"]["engine_used"] == "transformer"
    unawaited = [w for w in caught if "never awaited" in str(w.message).lower()]
    assert not unawaited


def test_extract_tables_from_pdf_scan_multi_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy")

    page1 = Image.new("RGB", (32, 32), color="white")
    page2 = Image.new("RGB", (32, 32), color="black")
    detected = SimpleNamespace(value="pdf_scan")

    call_pages: list[int] = []

    async def fake_parser(image: Image.Image, **kwargs) -> dict:
        call_pages.append(1 if image.getpixel((0, 0)) == (255, 255, 255) else 2)
        return {
            "success": True,
            "tables": [
                {
                    "columns": ["Col"],
                    "data": [[f"p{call_pages[-1]}"]],
                    "score": 0.9,
                    "bbox": [0, 0, 10, 10],
                }
            ],
        }

    with patch(
        "app.services.image_table_pipeline.raster_table_extraction_enabled",
        return_value=True,
    ), patch(
        "app.services.image_table_pipeline._transformer_available",
        return_value=True,
    ), patch(
        "app.services.image_table_pipeline._run_transformer_parser",
        fake_parser,
    ), patch(
        "app.services.image_table_pipeline.detect_file_type",
        return_value=(detected, 2),
    ), patch(
        "app.services.image_table_pipeline.load_raster_pages",
        return_value=[(1, page1), (2, page2)],
    ):
        result = extract_tables_from_image(pdf_path, pages_spec="1,2", max_pages=10)

    assert len(result["tables"]) == 2
    assert {t["page"] for t in result["tables"]} == {1, 2}
    assert result["routing"]["table_type_detected"] == "pdf_scan"
    assert result["quality"]["pages_processed"] == 2


def test_extract_tables_from_image_transformer_unavailable() -> None:
    with patch(
        "app.services.image_table_pipeline._transformer_available",
        return_value=False,
    ), patch(
        "app.services.image_table_pipeline.raster_table_extraction_enabled",
        return_value=True,
    ):
        with pytest.raises(RuntimeError, match="ocr-heavy"):
            extract_tables_from_image(Path("dummy.png"))


def test_extract_tables_from_image_raises_when_frozen() -> None:
    with patch(
        "app.services.image_table_pipeline.raster_table_extraction_enabled",
        return_value=False,
    ):
        with pytest.raises(RuntimeError, match="disabled in Lite"):
            extract_tables_from_image(Path("dummy.png"))
