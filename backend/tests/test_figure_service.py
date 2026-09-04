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
    _detect_bbox_space_mismatch,
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
        # Crop matches the layout detection box (no pad).
        assert item["width_px"] == 560
        assert item["height_px"] == 400
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

    def test_duplicate_id_across_pages_suffixed(self, sample_pdf, tmp_path):
        """Defense: if two figures share an id (legacy worker regression),
        the second crop is suffixed with the page number so it does not
        overwrite the first crop file."""
        layout = {
            "elements": [
                _fig_elem("p1_e0", 1, 100, 100, 200, 150),
                _fig_elem("p1_e0", 2, 100, 100, 200, 150),  # same id, page 2
            ]
        }
        result = FigureService().crop_figures(
            file_path=sample_pdf, layout_result=layout,
            output_dir=str(tmp_path / "f"), task_id="t_dup",
        )
        assert result["cropped_count"] == 2
        ids = [f["id"] for f in result["figures"]]
        # Second figure id must be suffixed to avoid collision.
        assert ids[0] == "p1_e0"
        assert ids[1] == "p1_e0_p2"
        # Both crop files must exist on disk (no overwrite).
        assert os.path.isfile(os.path.join(str(tmp_path / "f"), "p1_e0.png"))
        assert os.path.isfile(os.path.join(str(tmp_path / "f"), "p1_e0_p2.png"))
        # crop_url reflects the suffixed id.
        assert result["figures"][1]["crop_url"] == "/api/v1/tasks/t_dup/figures/p1_e0_p2"

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


class TestBboxSpaceMismatch:
    """Coordinate-space self-check: flag bboxes that exceed the raster."""

    def _fig(self, fid, page, x, y, w, h, etype="figure"):
        return {
            "id": fid,
            "page": page,
            "type": etype,
            "bbox": {"x": x, "y": y, "width": w, "height": h},
        }

    def _pages(self, page_no, w, h):
        # pages dict maps page_no -> (img_sentinel, width, height)
        return {page_no: (None, w, h)}

    def test_in_bounds_no_warning(self):
        figs = [self._fig("p1_e1", 1, 100, 100, 500, 400)]  # max x=600, y=500
        pages = self._pages(1, 1191, 1684)
        assert _detect_bbox_space_mismatch(figs, pages) == []

    def test_over_width_warns(self):
        # bbox max x = 1300 > raster width 1191 (tolerance 3)
        figs = [self._fig("p1_e1", 1, 100, 100, 1200, 400)]
        pages = self._pages(1, 1191, 1684)
        warnings = _detect_bbox_space_mismatch(figs, pages)
        assert len(warnings) == 1
        w = warnings[0]
        assert w["kind"] == "bbox_space_mismatch"
        assert w["page"] == 1
        assert w["id"] == "p1_e1"
        assert w["over_w"] is True
        assert w["over_h"] is False
        assert w["raster"] == {"width": 1191, "height": 1684}

    def test_over_height_warns(self):
        # bbox max y = 1800 > raster height 1684
        figs = [self._fig("p1_e2", 1, 100, 100, 400, 1700)]
        pages = self._pages(1, 1191, 1684)
        warnings = _detect_bbox_space_mismatch(figs, pages)
        assert len(warnings) == 1
        assert warnings[0]["over_h"] is True
        assert warnings[0]["over_w"] is False

    def test_swapped_dims_flagged(self):
        # Rotated-space signature: over width but height fits -> swapped
        figs = [self._fig("p1_e3", 1, 100, 100, 1600, 1000)]  # max x=1700>1191, y=1100<1684
        pages = self._pages(1, 1191, 1684)
        warnings = _detect_bbox_space_mismatch(figs, pages)
        assert len(warnings) == 1
        assert warnings[0]["swapped_dims"] is True

    def test_missing_page_skipped(self):
        # page not in pages dict -> no warning (reported as error elsewhere)
        figs = [self._fig("p9_e1", 9, 100, 100, 500, 400)]
        pages = self._pages(1, 1191, 1684)
        assert _detect_bbox_space_mismatch(figs, pages) == []

    def test_tolerance_allows_small_overflow(self):
        # 2px overflow within 3px tolerance -> no warning
        figs = [self._fig("p1_e1", 1, 100, 100, 1090, 400)]  # max x=1190, raster 1191
        pages = self._pages(1, 1191, 1684)
        assert _detect_bbox_space_mismatch(figs, pages) == []


class TestNoSilentPageFallback:
    """crop_figures must NOT fall back to page 1 when page_no is missing.

    Previously `source = pages.get(page_no) or pages.get(1)` silently cropped
    every page-mismatched figure from page 1's raster, producing many
    identical crops. Now a missing page surfaces as a per-figure error.
    """

    def test_missing_page_records_error_not_page1_crop(self, sample_pdf, tmp_path):
        layout = {
            "elements": [
                _fig_elem("p9_e1", 9, 200, 400, 560, 400),  # page 9 not rendered
            ]
        }
        out_dir = str(tmp_path / "figures")
        res = FigureService().crop_figures(
            file_path=sample_pdf,
            layout_result=layout,
            output_dir=out_dir,
            task_id="t1",
        )
        # No crop produced for the missing-page figure
        assert res["cropped_count"] == 0
        assert res["figure_count"] == 1
        # An error must be recorded mentioning page 9 and rendered pages
        assert res["errors"], "expected a per-figure error for missing page"
        err = res["errors"][0]
        assert "page 9" in err["reason"]
        assert "rendered pages" in err["reason"]
        # And a bbox_space_mismatch warning is NOT raised for it (page absent)
        assert not any(w["kind"] == "bbox_space_mismatch" for w in res["warnings"])


class TestMergedCrop:
    """F-merge: crop_figures consumes split warnings and emits a merged crop."""

    def test_vertical_split_produces_merged_crop(self, sample_pdf, tmp_path):
        # Two stacked figure halves that detect_split_warnings flags as a
        # vertical split (same x-extent, small gap). crop_figures must emit a
        # third "merged_figure" item covering the union bbox.
        layout = {
            "elements": [
                _fig_elem("a", 1, 200, 200, 400, 300),
                _fig_elem("b", 1, 200, 515, 400, 300),
            ]
        }
        out_dir = str(tmp_path / "figures")
        result = FigureService().crop_figures(
            file_path=sample_pdf, layout_result=layout, output_dir=out_dir, task_id="tm1"
        )
        # Two original halves + one merged crop.
        assert result["figure_count"] == 2
        assert result["cropped_count"] == 2
        assert result.get("merged_count") == 1
        merged = [f for f in result["figures"] if f.get("is_merged")]
        assert len(merged) == 1
        m = merged[0]
        assert m["type"] == "merged_figure"
        assert set(m["merged_from"]) == {"a", "b"}
        assert m["split_kind"] == "possible_vertical_split"
        # Merged bbox is the union: x=200, y=200, w=400, h=615 (300+gap15+300).
        assert m["bbox"]["x"] == 200
        assert m["bbox"]["width"] == 400
        assert m["bbox"]["height"] == 615
        assert os.path.isfile(m["crop_path"])
        assert m["crop_url"] == "/api/v1/tasks/tm1/figures/merged_a_b"

    def test_original_halves_kept_as_fallback(self, sample_pdf, tmp_path):
        layout = {
            "elements": [
                _fig_elem("a", 1, 200, 200, 400, 300),
                _fig_elem("b", 1, 200, 515, 400, 300),
            ]
        }
        result = FigureService().crop_figures(
            file_path=sample_pdf, layout_result=layout,
            output_dir=str(tmp_path / "f"), task_id="tm2",
        )
        # Both original halves remain in the figures list (fallback).
        ids = [f["id"] for f in result["figures"]]
        assert "a" in ids and "b" in ids
        assert "merged_a_b" in ids

    def test_nested_regions_not_merged(self, sample_pdf, tmp_path):
        # A caption/inner box fully inside a figure is nested_regions, NOT a
        # split — must not produce a merged crop.
        layout = {
            "elements": [
                _fig_elem("outer", 1, 200, 200, 400, 400),
                _fig_elem("inner", 1, 250, 250, 100, 100),
            ]
        }
        result = FigureService().crop_figures(
            file_path=sample_pdf, layout_result=layout,
            output_dir=str(tmp_path / "f"), task_id="tm3",
        )
        assert result.get("merged_count", 0) == 0
        assert not any(f.get("is_merged") for f in result["figures"])

    def test_far_apart_no_merge(self, sample_pdf, tmp_path):
        layout = {
            "elements": [
                _fig_elem("a", 1, 100, 100, 200, 100),
                _fig_elem("b", 1, 100, 1200, 200, 100),
            ]
        }
        result = FigureService().crop_figures(
            file_path=sample_pdf, layout_result=layout,
            output_dir=str(tmp_path / "f"), task_id="tm4",
        )
        assert result.get("merged_count", 0) == 0

    def test_merged_crop_in_pipeline_step(self, sample_pdf, tmp_path, monkeypatch):
        import asyncio

        from app.core.config import settings as _settings
        from app.orchestration.document_pipeline_orchestrator import figure_step

        monkeypatch.setattr(_settings, "OUTPUT_DIR", str(tmp_path))
        layout = {
            "elements": [
                _fig_elem("a", 1, 200, 200, 400, 300),
                _fig_elem("b", 1, 200, 515, 400, 300),
            ]
        }
        ctx = {
            "orchestrator": _StubOrchestrator(),
            "task_id": "stepTm",
            "task": {"file_path": sample_pdf},
            "file_path": sample_pdf,
            "result": {"layout": layout, "document_info": {}},
            "options": {},
        }
        asyncio.run(figure_step(ctx))
        figures = ctx["result"]["figures"]
        assert figures["merged_count"] == 1
        merged_items = [i for i in figures["items"] if i["is_merged"]]
        assert len(merged_items) == 1
        assert set(merged_items[0]["merged_from"]) == {"a", "b"}
        # Disk paths must not leak into the API-facing dict.
        assert "crop_path" not in merged_items[0]


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
