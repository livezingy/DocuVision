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

    async def fake_parser(_image: Image.Image) -> dict:
        return mock_result

    with patch(
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


def test_extract_tables_from_image_transformer_unavailable() -> None:
    with patch(
        "app.services.image_table_pipeline._transformer_available",
        return_value=False,
    ):
        with pytest.raises(RuntimeError, match="ocr-heavy"):
            extract_tables_from_image(Path("dummy.png"))
