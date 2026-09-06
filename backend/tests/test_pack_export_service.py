"""Unit tests for single-task artifact ZIP packing.

No Paddle / GPU. Uses a 1x1 PNG fixture and in-memory table dicts.
"""

from __future__ import annotations

import asyncio
import json
import zipfile
from pathlib import Path

import pytest

from app.services.pack_export_service import (
    PackTooLargeError,
    build_task_pack_zip,
    parse_include,
    render_single_table_csv,
    single_table_csv_filename,
)

# 1x1 PNG (same bytes Excel/zip tests can copy without an image library).
_MINI_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _result(*, tables=None, figures=None, file_name="demo.pdf"):
    return {
        "document_info": {"file_name": file_name},
        "tables": tables if tables is not None else [
            {
                "page": 16,
                "confidence": 0.87,
                "caption": "Ablation",
                "data": [["H1", "+pos"], ["a", "b"]],
            }
        ],
        "figures": figures if figures is not None else {
            "figure_count": 1,
            "cropped_count": 1,
            "items": [
                {
                    "id": "p1_e3",
                    "page": 1,
                    "type": "figure",
                    "caption": "Flow",
                    "confidence": 0.9,
                    "is_merged": False,
                }
            ],
        },
        "quality": {"figure_count": 1, "figure_cropped_count": 1},
    }


def _pack(tmp_path: Path, result, **kwargs) -> Path:
    figures_dir = kwargs.pop("figures_dir", tmp_path / "crops")
    figures_dir.mkdir(parents=True, exist_ok=True)
    if "skip_png" not in kwargs:
        (figures_dir / "p1_e3.png").write_bytes(_MINI_PNG)
    kwargs.pop("skip_png", None)
    path = asyncio.run(
        build_task_pack_zip(
            result,
            "task1",
            output_dir=str(tmp_path),
            figures_dir=str(figures_dir),
            **kwargs,
        )
    )
    return Path(path)


class TestParseInclude:
    def test_default(self):
        assert parse_include(None) == {"tables", "figures"}
        assert parse_include("") == {"tables", "figures"}
        assert parse_include("  ") == {"tables", "figures"}

    def test_explicit(self):
        assert parse_include("tables,json") == {"tables", "json"}

    def test_rejects_unknown(self):
        with pytest.raises(ValueError, match="seals"):
            parse_include("tables,seals")


class TestSingleTableCsv:
    def test_filename_and_banner(self):
        table = {"page": 16, "confidence": 0.87, "caption": "Ablation", "data": [["H", "+x"]]}
        assert single_table_csv_filename(1, 16) == "table_01_p16.csv"
        text = render_single_table_csv(1, table)
        assert "=== Table 1 (Page 16) confidence=87% ===" in text
        assert "Caption: Ablation" in text
        assert "'+x" in text


class TestBuildTaskPackZip:
    def test_default_pack_layout(self, tmp_path):
        path = _pack(tmp_path, _result())
        assert path.name == "task1_pack.zip"
        assert path.read_bytes()[:2] == b"PK"
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            assert "manifest.json" in names
            assert "tables/tables.csv" in names
            assert "tables/table_01_p16.csv" in names
            assert "figures/index.csv" in names
            assert "figures/p1_e3.png" in names
            assert "result.json" not in names
            manifest = json.loads(zf.read("manifest.json"))
        assert manifest["task_id"] == "task1"
        assert manifest["file_name"] == "demo.pdf"
        assert manifest["table_count"] == 1
        assert manifest["packed_figure_files"] == 1
        assert manifest["missing_figures"] == []
        assert set(manifest["include"]) == {"figures", "tables"}

    def test_include_tables_omits_figure_pngs(self, tmp_path):
        path = _pack(tmp_path, _result(), include="tables")
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        assert any(n.startswith("tables/") for n in names)
        assert not any(n.endswith(".png") for n in names)
        assert "figures/index.csv" not in names

    def test_include_json(self, tmp_path):
        path = _pack(tmp_path, _result(), include="json")
        with zipfile.ZipFile(path) as zf:
            payload = json.loads(zf.read("result.json"))
        assert payload["document_info"]["file_name"] == "demo.pdf"

    def test_merged_figure_goes_to_subdir(self, tmp_path):
        crops = tmp_path / "crops"
        crops.mkdir()
        (crops / "m_p1.png").write_bytes(_MINI_PNG)
        result = _result(
            figures={
                "figure_count": 1,
                "cropped_count": 1,
                "items": [
                    {
                        "id": "m_p1",
                        "page": 1,
                        "type": "figure",
                        "is_merged": True,
                    }
                ],
            }
        )
        path = _pack(tmp_path, result, figures_dir=crops, skip_png=True)
        with zipfile.ZipFile(path) as zf:
            assert "figures/merged/m_p1.png" in zf.namelist()

    def test_missing_crop_listed_not_fatal(self, tmp_path):
        path = _pack(tmp_path, _result(), skip_png=True)
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            manifest = json.loads(zf.read("manifest.json"))
        assert "figures/p1_e3.png" not in names
        assert "p1_e3" in manifest["missing_figures"]
        assert "tables/tables.csv" in names

    def test_rejects_unsafe_task_id(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid task id"):
            asyncio.run(
                build_task_pack_zip(_result(), "../evil", output_dir=str(tmp_path))
            )

    def test_pack_too_large_removes_partial(self, tmp_path):
        with pytest.raises(PackTooLargeError):
            _pack(tmp_path, _result(), max_bytes=8)
        assert not (tmp_path / "task1_pack.zip").exists()
