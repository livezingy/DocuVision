"""F1 reading-order tests (pure logic, no Paddle/GPU).

Covers:
- ``app.services._layout_order`` sort key / mixed-case policy.
- ``orchestration.envelope_builder`` view layer: prefers ``reading_order``
  carried from layout (block_order) over the naive per-page counter.

Official basis: ``parsing_res_list`` list order IS the reading order and each
block carries ``block_order`` — see
https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md
and findings §1.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Pure helper module — no paddle import.
_ORDER_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "_layout_order.py"
_spec = importlib.util.spec_from_file_location("_layout_order_for_tests", _ORDER_PATH)
assert _spec is not None and _spec.loader is not None
_order_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_order_mod)

reading_order_sort_key = _order_mod.reading_order_sort_key
sort_elements_by_reading_order = _order_mod.sort_elements_by_reading_order
has_reading_order = _order_mod.has_reading_order


def _elem(eid: str, ro: Any, y: float, x: float) -> Dict[str, Any]:
    return {"id": eid, "reading_order": ro, "bbox": {"y": y, "x": x}}


# ---------------------------------------------------------------------------
# _layout_order pure logic
# ---------------------------------------------------------------------------

class TestLayoutOrderPure:
    def test_sort_by_reading_order_when_present(self) -> None:
        # Two-column page: naive (y,x) would interleave; block_order is correct.
        elems = [
            _elem("left_top", 0, y=10, x=0),
            _elem("right_top", 2, y=10, x=400),
            _elem("left_bottom", 1, y=200, x=0),
            _elem("right_bottom", 3, y=200, x=400),
        ]
        out = sort_elements_by_reading_order(elems)
        assert [e["id"] for e in out] == ["left_top", "left_bottom", "right_top", "right_bottom"]

    def test_fallback_to_yx_when_no_reading_order(self) -> None:
        elems = [
            _elem("b", None, y=200, x=0),
            _elem("a", None, y=10, x=0),
            _elem("c", None, y=10, x=400),
        ]
        out = sort_elements_by_reading_order(elems)
        # (y, x): a(10,0), c(10,400), b(200,0)
        assert [e["id"] for e in out] == ["a", "c", "b"]

    def test_mixed_reading_order_groups_first(self) -> None:
        # Elements with reading_order sort first (group 0), then fallback (group 1).
        elems = [
            _elem("fallback", None, y=5, x=0),
            _elem("ro1", 1, y=999, x=0),
            _elem("ro0", 0, y=999, x=0),
        ]
        out = sort_elements_by_reading_order(elems)
        assert [e["id"] for e in out] == ["ro0", "ro1", "fallback"]

    def test_has_reading_order_detection(self) -> None:
        assert has_reading_order([_elem("a", 0, 0, 0), _elem("b", None, 0, 0)]) is True
        assert has_reading_order([_elem("a", None, 0, 0)]) is False

    def test_none_reading_order_treated_as_fallback(self) -> None:
        # reading_order=None must NOT be coerced to 0 (which would collide with
        # a real block_order=0). It must fall into the fallback group.
        e = _elem("x", None, y=10, x=0)
        key = reading_order_sort_key(e)
        assert key[0] == 1  # fallback group, not reading_order group


# ---------------------------------------------------------------------------
# envelope_builder view layer (loadable: numpy present, cv2 optional)
# ---------------------------------------------------------------------------

_ENV_PATH = Path(__file__).resolve().parents[1] / "app" / "orchestration" / "envelope_builder.py"
_eb_spec = importlib.util.spec_from_file_location("envelope_builder_for_tests", _ENV_PATH)
assert _eb_spec is not None and _eb_spec.loader is not None
_eb_mod = importlib.util.module_from_spec(_eb_spec)
_eb_spec.loader.exec_module(_eb_mod)
EnvelopeBuilder = _eb_mod.EnvelopeBuilder


def _make_layout_result(elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "engine": "PP-StructureV3",
        "total_pages": 1,
        "elements": elements,
        "page_layouts": [{"page": 1}],
        "summary": {},
        "output_size": {"width": 1000, "height": 1400},
        "input_size": {"width": 1000, "height": 1400},
    }


def _elem_for_fused(eid: str, etype: str, ro: Any, y: float, x: float) -> Dict[str, Any]:
    return {
        "id": eid,
        "page": 1,
        "type": etype,
        "bbox": {"x": x, "y": y, "width": 100, "height": 50},
        "polygon_preprocessed": [x, y, x + 100, y, x + 100, y + 50, x, y + 50],
        "confidence": 0.9,
        "reading_order": ro,
        "text": "t",
    }


class TestEnvelopeBuilderReadingOrder:
    def _build(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        builder = EnvelopeBuilder.__new__(EnvelopeBuilder)
        layout = _make_layout_result(elements)
        preprocessing = {
            "coordinate_space": "original",
            "angle_deg": 0.0,
            "use_doc_unwarping": False,
            "input_size": {"width": 1000, "height": 1400},
            "output_size": {"width": 1000, "height": 1400},
        }
        fused = builder.build_fused_layer(layout_result=layout)
        view = builder.build_view_layer(
            fused_layer=fused,
            preprocessing_metadata=preprocessing,
            original_image_path="x.pdf",
            preprocessed_image_path="x.pdf",
        )
        return view

    def test_view_uses_reading_order_from_layout(self) -> None:
        # Two-column: block_order gives correct column-major order.
        elems = [
            _elem_for_fused("left_top", "text", 0, y=10, x=0),
            _elem_for_fused("right_top", "text", 2, y=10, x=400),
            _elem_for_fused("left_bottom", "text", 1, y=200, x=0),
            _elem_for_fused("right_bottom", "text", 3, y=200, x=400),
        ]
        view = self._build(elems)
        page_elements = view["pages"][0]["elements"]
        ordered = sorted(page_elements, key=lambda e: e["reading_order"])
        ids = [e["id"] for e in ordered]
        assert ids == ["left_top", "left_bottom", "right_top", "right_bottom"]

    def test_view_falls_back_to_counter_when_no_reading_order(self) -> None:
        elems = [
            _elem_for_fused("a", "text", None, y=200, x=0),
            _elem_for_fused("b", "text", None, y=10, x=0),
        ]
        view = self._build(elems)
        page_elements = view["pages"][0]["elements"]
        # fused layer preserves element order; view counter assigns 0,1 in that
        # order (no block_order to reorder). Both must have distinct orders.
        orders = {e["id"]: e["reading_order"] for e in page_elements}
        assert len(set(orders.values())) == 2

    def test_fused_layer_carries_reading_order(self) -> None:
        elems = [_elem_for_fused("a", "text", 5, y=10, x=0)]
        view = self._build(elems)
        assert view["pages"][0]["elements"][0]["reading_order"] == 5
