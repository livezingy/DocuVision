"""Tests for coordinate alignment in selective backfill (v1.8 §4.2)."""

from __future__ import annotations

import fitz

from app.services.table_backfill import (
    _extract_cell_text_layer,
    backfill_tables,
    derive_cell_bbox,
)


def test_derive_cell_bbox_px_to_pt() -> None:
    bbox = {"x": 0, "y": 0, "width": 200, "height": 100}  # raster px (Matrix 2x2)
    # PDF pt = px / 2 -> 100 x 50; 2x2 grid -> 50 x 25 cells
    assert derive_cell_bbox(bbox, 2, 2, 0, 0) == (0.0, 0.0, 50.0, 25.0)
    assert derive_cell_bbox(bbox, 2, 2, 1, 1) == (50.0, 25.0, 100.0, 50.0)
    assert derive_cell_bbox(bbox, 2, 2, 0, 1) == (50.0, 0.0, 100.0, 25.0)


def test_derive_cell_bbox_degenerate_returns_none() -> None:
    assert derive_cell_bbox({"x": 0, "y": 0, "width": 0, "height": 0}, 2, 2, 0, 0) is None
    assert derive_cell_bbox({"x": 0, "y": 0, "width": 100, "height": 100}, 0, 2, 0, 0) is None


def test_extract_cell_text_layer_rejects_crossing_word() -> None:
    bbox = (0.0, 0.0, 50.0, 25.0)
    words = [[45, 10, 55, 20, "text", 0, 0, 0]]  # x1=55 crosses right edge
    in_cell, lines = _extract_cell_text_layer(words, bbox)
    assert in_cell is None
    assert lines is None


def test_extract_cell_text_layer_accepts_contained_word() -> None:
    bbox = (0.0, 0.0, 50.0, 25.0)
    words = [[10, 10, 40, 20, "text", 0, 0, 0]]
    in_cell, lines = _extract_cell_text_layer(words, bbox)
    assert in_cell is not None
    assert len(in_cell) == 1
    assert lines == {0}


def _make_rotated_pdf(path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 80), "visible text", fontsize=11)
    page.set_rotation(90)
    doc.save(path)
    doc.close()


def test_backfill_tables_skips_rotated_page(tmp_path) -> None:
    path = str(tmp_path / "rotated.pdf")
    _make_rotated_pdf(path)
    tables = [
        {
            "id": "t1",
            "page": 1,
            "bbox": {"x": 0, "y": 0, "width": 200, "height": 100},
            "data": [["1234"]],
        }
    ]
    summary = backfill_tables(tables, path, enabled=True)
    assert summary["enabled"] is True
    # page is trusted text_layer but rotated -> backfill skipped
    assert summary["pages_text_layer_trusted"] == 0
    assert summary["cells_candidates"] == 0
