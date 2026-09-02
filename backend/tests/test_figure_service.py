"""Unit tests for FigureService cropping + integrity checks (GLM trial P0-2).

Uses PyMuPDF to build a synthetic 2-page PDF whose page raster geometry is
known (A4 @ 2x matrix = 1191x1684 px), plus a synthetic PNG. No Paddle /
GPU involved — layout elements are injected manually, mirroring the real
layout_service element contract (type / bbox / page / confidence).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import pytest

from app.services.figure_service import (
    FIGURE_LABELS,
    FigureService,
    detect_split_warnings,
)

A4_W_PT = 595
A4_H_PT = 842
# fitz.Matrix(2, 2) on A4 → pixel size
PIX_W = A4_W_PT * 2
PIX_H = A4_H_PT * 2


@pytest.fixture()
def sample_pdf(tmp_path) -> str:
    import fitz

    path = str(tmp_path / "techdoc.pdf")
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page(width=A4_W_PT, height=A4_H_PT)
        # Draw a filled rect "diagram" in the middle of the page.
        page.draw_rect(fitz.Rect(100, 200, 480, 400), color=(0.2, 0.4, 0.8), fill=(0.85, 0.9, 0.98), width=2)
        page.insert_text((120, 250), "PROCESS DIAGRAM", fontsize=14)
    doc.save(path)
    doc.close()
    return path


def _fig_elem(elem_id: str, page: int, x: float, y: float, w: float, h: float, etype: str = "figure") -> Dict[str, Any]:
    return {
        "id": elem_id,
        "page": page,
        "type": etype,
        "type_name": "Figure",
        "bbox": {"x": x, "y": y, "width": w, "height": h},
        "confidence": 0.92,
    }


class TestCropFiguresPdf:
    def test_pdf_figure_crop_roundtrip(self, sample_pdf, tmp_path):
        layout = {
            "elements": [
                _fig_elem("p1_e2", 1, 200, 400, 560, 400),  # matches drawn rect (2x pt)
                {"id": "p1_e1", "page": 1, "type": "text", "bbox": {"x": 0, "y": 0, "width": 10, "height": 10}},
            ]
        }
        out_dir = str(tmp_path / "figures")
        result = FigureService().crop_figures(
            file_path=sample_pdf, layout_result=layout, output_dir=out_dir, task_id="t1"
        )
        assert result["figure_count"] == 1
        assert result["cropped_count"] == 1
        item = result["figures"][0]
        assert item["id"] == "p1_e2"
        assert item["width_px"] == 560 and item["height_px"] == 400
        assert os.path.isfile(item["crop_path"])
        assert item["crop_url"] == "/api/v1/tasks/t1/figures/p1_e2"
        assert result["errors"] == []

    def test_multi_page_pdf(self, sample_pdf, tmp_path):
        layout = {
            "elements": [
                _fig_elem("p1_e0", 1, 100, 100, 200, 150),
                _fig_elem("p2_e1", 2, 100, 100, 200, 150),
            ]
        }
        result = FigureService().crop_figures(
            file_path=sample_pdf, layout_result=layout,
            output_dir=str(tmp_path / "f"), task_id="t2",
        )
        assert result["cropped_count"] == 2
        pages = {f["page"] for f in result["figures"]}
        assert pages == {1, 2}

    def test_bbox_clamped_to_page_bounds(self, sample_pdf, tmp_path):
        layout = {"elements": [_fig_elem("p1_e0", 1, PIX_W - 10, PIX_H - 10, 500, 500)]}
        result = FigureService().crop_figures(
            file_path=sample_pdf, layout_result=layout,
            output_dir=str(tmp_path / "f"), task_id="t3",
        )
        item = result["figures"][0]
        assert item["width_px"] <= 10 and item["height_px"] <= 10

    def test_degenerate_bbox_skipped(self, sample_pdf, tmp_path):
        layout = {"elements": [_fig_elem("p1_e0", 1, 10, 10, 2, 2)]}
        result = FigureService().crop_figures(
            file_path=sample_pdf, layout_result=layout,
            output_dir=str(tmp_path / "f"), task_id="t4",
        )
        assert result["figure_count"] == 1
        assert result["cropped_count"] == 0

    def test_no_figures_is_noop(self, sample_pdf, tmp_path):
        layout = {"elements": [{"id": "p1_e0", "page": 1, "type": "text", "bbox": {"x": 0, "y": 0, "width": 5, "height": 5}}]}
        result = FigureService().crop_figures(
            file_path=sample_pdf, layout_result=layout,
            output_dir=str(tmp_path / "f"), task_id="t5",
        )
        assert result["figure_count"] == 0
        assert result["cropped_count"] == 0


class TestCropFiguresImage:
    def test_image_crop_uses_preprocessed_path(self, tmp_path):
        from PIL import Image

        img_path = tmp_path / "scan.png"
        Image.new("RGB", (800, 600), (250, 250, 250)).save(img_path)

        prep_path = tmp_path / "prep.png"
        Image.new("RGB", (800, 600), (10, 10, 10)).save(prep_path)

        layout = {
            "elements": [_fig_elem("p1_e1", 1, 100, 100, 200, 200)],
            "preprocessed_image_path": str(prep_path),
        }
        result = FigureService().crop_figures(
            file_path=str(img_path), layout_result=layout,
            output_dir=str(tmp_path / "f"), task_id="t6",
        )
        assert result["cropped_count"] == 1
        assert result["source"]["mode"] == "image"
        assert result["source"]["preprocessed"] is True

    def test_image_crop_falls_back_to_original(self, tmp_path):
        from PIL import Image

        img_path = tmp_path / "scan.png"
        Image.new("RGB", (800, 600), (250, 250, 250)).save(img_path)
        layout = {"elements": [_fig_elem("p1_e1", 1, 100, 100, 200, 200)]}
        result = FigureService().crop_figures(
            file_path=str(img_path), layout_result=layout,
            output_dir=str(tmp_path / "f"), task_id="t7",
        )
        assert result["cropped_count"] == 1
        assert result["source"]["preprocessed"] is False

    def test_missing_source_records_error_not_raise(self, tmp_path):
        layout = {"elements": [_fig_elem("p1_e1", 1, 100, 100, 200, 200)]}
        result = FigureService().crop_figures(
            file_path=str(tmp_path / "nope.png"), layout_result=layout,
            output_dir=str(tmp_path / "f"), task_id="t8",
        )
        assert result["figure_count"] == 1
        assert result["cropped_count"] == 0
        assert result["errors"]


class TestFigureLabels:
    def test_expected_labels_included(self):
        for label in ("figure", "image", "chart", "flowchart", "picture"):
            assert label in FIGURE_LABELS

    def test_seal_excluded(self):
        assert "seal" not in FIGURE_LABELS


class TestIntegrityWarnings:
    def _box(self, fid, x, y, w, h):
        return {"id": fid, "bbox": {"x": x, "y": y, "width": w, "height": h}}

    def test_vertical_split_detected(self):
        # Two stacked boxes, similar x-extent, tiny gap → classic NMS split.
        boxes = [self._box("a", 100, 100, 400, 300), self._box("b", 100, 315, 400, 300)]
        warnings = detect_split_warnings(boxes, page_height=1684)
        assert any(w["kind"] == "possible_vertical_split" for w in warnings)

    def test_far_apart_no_warning(self):
        boxes = [self._box("a", 100, 100, 400, 100), self._box("b", 100, 1200, 400, 100)]
        assert detect_split_warnings(boxes, page_height=1684) == []

    def test_side_by_side_split_detected(self):
        boxes = [self._box("a", 100, 100, 200, 400), self._box("b", 310, 100, 200, 400)]
        warnings = detect_split_warnings(boxes, page_height=1684)
        assert any(w["kind"] == "possible_horizontal_split" for w in warnings)

    def test_different_rows_no_warning(self):
        # Vertical overlap low → not a horizontal split.
        boxes = [self._box("a", 100, 100, 200, 100), self._box("b", 310, 600, 200, 100)]
        assert detect_split_warnings(boxes, page_height=1684) == []

    def test_nested_containment_info(self):
        boxes = [self._box("outer", 100, 100, 400, 400), self._box("inner", 150, 150, 100, 100)]
        warnings = detect_split_warnings(boxes, page_height=1684)
        assert any(w["kind"] == "nested_regions" for w in warnings)

    def test_merged_bbox_suggestion(self):
        boxes = [self._box("a", 100, 100, 400, 300), self._box("b", 100, 315, 400, 300)]
        warnings = detect_split_warnings(boxes, page_height=1684)
        split = next(w for w in warnings if w["kind"] == "possible_vertical_split")
        assert split["merged_bbox"]["x"] == 100
        assert split["merged_bbox"]["width"] == 400
        assert split["merged_bbox"]["height"] == 515


# ---------------------------------------------------------------------------
# figure_step pipeline integration (mocked orchestrator, no engines)

class _StubOrchestrator:
    def ensure_not_cancelled(self, ctx):
        return None

    async def update_progress(self, ctx, progress, message):
        return None


def test_figure_step_populates_result(sample_pdf, tmp_path, monkeypatch):
    import asyncio

    from app.core.config import settings as _settings
    from app.orchestration.document_pipeline_orchestrator import figure_step

    monkeypatch.setattr(_settings, "OUTPUT_DIR", str(tmp_path))
    layout = {"elements": [_fig_elem("p1_e2", 1, 200, 400, 560, 400)]}
    ctx = {
        "orchestrator": _StubOrchestrator(),
        "task_id": "stepT1",
        "task": {"file_path": sample_pdf},
        "file_path": sample_pdf,
        "result": {"layout": layout, "document_info": {}},
        "options": {},
    }
    asyncio.run(figure_step(ctx))
    figures = ctx["result"]["figures"]
    assert figures["figure_count"] == 1
    assert figures["cropped_count"] == 1
    assert figures["items"][0]["crop_url"] == "/api/v1/tasks/stepT1/figures/p1_e2"
    # Disk paths must not leak into the API-facing dict.
    assert "crop_path" not in figures["items"][0]


def test_figure_step_nonfatal_on_error(sample_pdf, tmp_path, monkeypatch):
    import asyncio

    from app.core.config import settings as _settings
    from app.orchestration.document_pipeline_orchestrator import figure_step
    from app.services.figure_service import FigureService

    monkeypatch.setattr(_settings, "OUTPUT_DIR", str(tmp_path))

    def _boom(self, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(FigureService, "crop_figures", _boom)
    layout = {"elements": [_fig_elem("p1_e2", 1, 200, 400, 560, 400)]}
    ctx = {
        "orchestrator": _StubOrchestrator(),
        "task_id": "stepT2",
        "task": {"file_path": sample_pdf},
        "file_path": sample_pdf,
        "result": {"layout": layout, "document_info": {}},
        "options": {},
    }
    asyncio.run(figure_step(ctx))  # must not raise
    figures = ctx["result"]["figures"]
    assert figures["errors"] and figures["errors"][0]["reason"] == "boom"
