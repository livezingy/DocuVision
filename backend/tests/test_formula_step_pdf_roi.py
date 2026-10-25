"""
P-040 ① unit tests: page-aware formula ROI sourcing in steps/extraction.formula_step.

PDF inputs re-rasterize each page group via the pdf_raster shared leaf
(matrix_scale=2.0, 1-based page numbers, temp PNG deleted after use);
image inputs keep the preprocessed||original chain. All mocks — no paddle/GPU.
"""
import asyncio
import inspect
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.orchestration.steps import extraction
from app.orchestration.steps.perception import _collect_layout_blocks


def _formula_elem(eid, page, x=10, y=20, w=100, h=40):
    return {
        "id": eid,
        "type": "formula",
        "page": page,
        "bbox": {"x": x, "y": y, "width": w, "height": h},
        "reading_order": 3,
    }


class _FakeOrchestrator:
    def __init__(self, services):
        self.services = services
        self.progress = []

    def ensure_not_cancelled(self, ctx):
        return None

    async def update_progress(self, ctx, pct, msg):
        self.progress.append((pct, msg))

    async def call_maybe_async(self, fn, *args, **kwargs):
        result = fn(*args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result


class _FakeFormulaService:
    def __init__(self, results=None):
        self.calls = []
        self._results = results or []

    def recognize(self, image_path, **kwargs):
        self.calls.append({"image_path": image_path, **kwargs})
        if self._results:
            return self._results[len(self.calls) - 1]
        n = len(kwargs.get("layout_formula_boxes") or [])
        return {
            "ok": True,
            "stage": "roi_batch",
            "unwrapped_results": [
                {
                    "formula_res_list": [
                        {"formula_region_id": i + 1, "rec_formula": "E=mc^2", "dt_polys": [1, 2, 3, 4]}
                        for i in range(n)
                    ]
                }
            ],
            "stats": {
                "formula_count": n,
                "layout_formula_box_count": n,
                "roi_total": n,
                "roi_recognized": n,
                "label_hist": {"formula": n},
                "first_formula": "E=mc^2" if n else None,
            },
            "error_level": "none",
        }


def _run(ctx):
    asyncio.run(extraction.formula_step(ctx))
    return ctx


def _make_ctx(file_path, elements, task=None, service=None):
    service = service or _FakeFormulaService()
    ctx = {
        "options": {"enable_formula": True},
        "orchestrator": _FakeOrchestrator({"formula_service": service}),
        "result": {"layout": {"elements": elements}},
        "task": task or {},
        "file_path": file_path,
    }
    return ctx, service


class TestPageAwarePdfRoi:
    def test_pdf_pages_grouped_and_rasterized(self, monkeypatch, tmp_path):
        raster_calls = []
        png = tmp_path / "page.png"
        png.write_bytes(b"png")

        def fake_rasterize(file_path, page_num, *, matrix_scale=2.0):
            raster_calls.append((file_path, page_num, matrix_scale))
            return str(png), str(png)

        monkeypatch.setattr(extraction, "rasterize_pdf_page", fake_rasterize)

        ctx, service = _make_ctx(
            "doc.pdf",
            [_formula_elem("p1_e1", 1), _formula_elem("p1_e2", 1), _formula_elem("p2_e1", 2)],
        )
        _run(ctx)

        assert raster_calls == [("doc.pdf", 1, 2.0), ("doc.pdf", 2, 2.0)]
        assert len(service.calls) == 2
        assert [b["page"] for b in service.calls[0]["layout_formula_boxes"]] == [1, 1]
        assert [b["page"] for b in service.calls[1]["layout_formula_boxes"]] == [2]
        assert all(c["roi_source_image_path"] == str(png) for c in service.calls)
        # temp raster deleted after each page
        assert not os.path.exists(str(png))
        assert ctx["result"]["formula_meta"]["succeeded"] is True
        assert ctx["result"]["formula_stats"]["formula_count"] == 3
        assert ctx["result"]["formula_stats"]["layout_formula_box_count"] == 3
        assert ctx["result"]["formula_layout_boxes"][0]["reading_order"] == 3

    def test_image_input_keeps_preprocessed_chain(self, monkeypatch):
        def fail_rasterize(*a, **kw):
            raise AssertionError("rasterize must not run for image inputs")

        monkeypatch.setattr(extraction, "rasterize_pdf_page", fail_rasterize)
        ctx, service = _make_ctx(
            "scan.png",
            [_formula_elem("p1_e1", 1)],
            task={"preprocessed_image_path": "prep.png"},
        )
        _run(ctx)
        assert len(service.calls) == 1
        assert service.calls[0]["roi_source_image_path"] == "prep.png"

    def test_image_input_without_preprocessed_falls_back_to_original(self, monkeypatch):
        def fail_rasterize(*a, **kw):
            raise AssertionError("rasterize must not run for image inputs")

        monkeypatch.setattr(extraction, "rasterize_pdf_page", fail_rasterize)
        ctx, service = _make_ctx("scan.jpg", [_formula_elem("p1_e1", 1)], task={})
        _run(ctx)
        assert service.calls[0]["roi_source_image_path"] == "scan.jpg"

    def test_rasterize_failure_falls_back_to_pdf_path(self, monkeypatch):
        monkeypatch.setattr(
            extraction, "rasterize_pdf_page", lambda f, p, *, matrix_scale=2.0: (f, None)
        )
        ctx, service = _make_ctx("doc.pdf", [_formula_elem("p1_e1", 1)])
        _run(ctx)
        assert service.calls[0]["roi_source_image_path"] == "doc.pdf"

    def test_all_pages_fail_records_first_error(self, monkeypatch):
        monkeypatch.setattr(
            extraction, "rasterize_pdf_page", lambda f, p, *, matrix_scale=2.0: (f, None)
        )
        failing = _FakeFormulaService(results=[
            {
                "ok": False,
                "error": "boom",
                "error_level": "soft",
                "error_code": "runtime_error",
                "failure_stage": "inference",
            }
        ])
        ctx, _ = _make_ctx("doc.pdf", [_formula_elem("p1_e1", 1)], service=failing)
        _run(ctx)
        meta = ctx["result"]["formula_meta"]
        assert meta["succeeded"] is False
        assert meta["error_message"] == "boom"
        assert meta["error_code"] == "runtime_error"

    def test_partial_page_success_still_succeeds(self, monkeypatch):
        monkeypatch.setattr(
            extraction, "rasterize_pdf_page", lambda f, p, *, matrix_scale=2.0: (f, None)
        )
        mixed = _FakeFormulaService(results=[
            {
                "ok": True,
                "stage": "roi_batch",
                "unwrapped_results": [{"formula_res_list": [{"rec_formula": "a"}]}],
                "stats": {"formula_count": 1, "layout_formula_box_count": 1},
            },
            {
                "ok": False,
                "error": "page2 down",
                "error_level": "soft",
                "error_code": "runtime_error",
                "failure_stage": "inference",
            },
        ])
        ctx, _ = _make_ctx(
            "doc.pdf", [_formula_elem("p1_e1", 1), _formula_elem("p2_e1", 2)], service=mixed
        )
        _run(ctx)
        assert ctx["result"]["formula_meta"]["succeeded"] is True
        assert ctx["result"]["formula_stats"]["formula_count"] == 1
        assert len(ctx["result"]["formula_unwrapped_results"]) == 1


class TestCollectLayoutBlocksPassthrough:
    def test_page_and_reading_order_ride_along(self):
        boxes = _collect_layout_blocks(
            {"elements": [_formula_elem("p2_e5", 2)]},
            accepted_types={"formula"},
        )
        assert boxes[0]["page"] == 2
        assert boxes[0]["reading_order"] == 3
        assert boxes[0]["source_id"] == "p2_e5"
