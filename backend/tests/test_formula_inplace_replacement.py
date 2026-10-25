"""
P-040 ③ unit tests: in-place formula replacement (adapt + envelope merge).

build_formula_replacements maps ROI results back onto source layout blocks
(source_id keyed); apply_formula_replacements swaps skip_formula placeholders
in place — block_id / bbox / official reading_order survive, recognized
regions carry $$LaTeX$$ in payload.text (body-text flow, P-040 ③ ruling),
unrecognized regions degrade to formula_unrecognized instead of vanishing.
All mocks — no paddle/GPU.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.orchestration.envelope_builder import EnvelopeBuilder
from app.orchestration.steps.envelope import apply_formula_replacements
from app.services.formula_adapt import build_formula_replacements, formula_replacement_stats


class _FakeSettings:
    DEBUG_MODE = False
    DEBUG_OUTPUT_DIR = "backend/debug"
    DEBUG_KEEP_LAST_N = 10


builder = EnvelopeBuilder(_FakeSettings())


def _layout(elements):
    return {
        "elements": elements,
        "output_size": {"width": 1000, "height": 1400},
        "input_size": {"width": 1000, "height": 1400},
        "preprocessed_image_width": 1000,
        "preprocessed_image_height": 1400,
        "use_doc_orientation_classify": True,
        "angle_deg": 0.0,
    }


def _elem(eid, etype, page=1, text="hello", order=None):
    return {
        "id": eid,
        "type": etype,
        "page": page,
        "bbox": [10, 10, 100, 50],
        "polygon_preprocessed": [10, 10, 100, 10, 100, 50, 10, 50],
        "text": text,
        "confidence": 0.9,
        "reading_order": order,
    }


def _unwrapped(items):
    """One unwrapped result item; items = [(source_id, latex), ...]."""
    return [
        {
            "formula_res_list": [
                {
                    "formula_region_id": i + 1,
                    "rec_formula": latex,
                    "dt_polys": [1, 2, 3, 4],
                    "source": "layout_roi",
                    "source_id": sid,
                }
                for i, (sid, latex) in enumerate(items)
            ]
        }
    ]


def _three_block_fused():
    """text(order 1) / formula placeholder(order 2) / text(order 3)."""
    elements = [
        _elem("p1_e1", "text", text="para one", order=1),
        _elem("p1_e2", "formula", text="", order=2),
        _elem("p1_e3", "text", text="para two", order=3),
    ]
    return builder.build_fused_layer(_layout(elements)), elements


def _block(fused, bid):
    for page in fused["pages"]:
        for b in page["blocks"]:
            if b["block_id"] == bid:
                return b
    raise KeyError(bid)


class TestBuildReplacements:
    def test_keyed_by_source_id(self):
        reps = build_formula_replacements(_unwrapped([("p1_e2", "E=mc^2")]), [])
        assert reps == {"p1_e2": {"latex": "E=mc^2", "formula_region_id": 1}}

    def test_empty_latex_becomes_none(self):
        reps = build_formula_replacements(_unwrapped([("p1_e2", "")]), [])
        assert reps["p1_e2"]["latex"] is None

    def test_first_occurrence_wins(self):
        reps = build_formula_replacements(
            _unwrapped([("p1_e2", "a"), ("p1_e2", "b")]), []
        )
        assert reps["p1_e2"]["latex"] == "a"

    def test_missing_source_id_skipped(self):
        item = [{"formula_res_list": [{"rec_formula": "x", "source_id": ""}]}]
        assert build_formula_replacements(item, []) == {}

    def test_stats(self):
        reps = {"a": {"latex": "x"}, "b": {"latex": None}}
        assert formula_replacement_stats(reps) == {
            "formula_blocks_total": 2,
            "formula_blocks_recognized": 1,
        }


class TestApplyInPlace:
    def test_recognized_swap_keeps_identity(self):
        fused, _ = _three_block_fused()
        apply_formula_replacements(
            fused, {"p1_e2": {"latex": "E=mc^2", "formula_region_id": 1}}
        )
        blk = _block(fused, "p1_e2")
        assert blk["payload"]["text"] == "$$E=mc^2$$"
        assert blk["payload"]["latex"] == "E=mc^2"
        assert blk["payload"]["mathml"] is None
        assert blk["processing_status"] == "recognized"
        assert blk["source"] == "formula_recognition"
        assert blk["provenance"]["merge_strategy"] == "recognized_by_optional_engine"
        assert blk["provenance"]["primary_source"] == "formula_recognition"
        # identity survives: id, geometry, official reading order, list position
        assert blk["block_id"] == "p1_e2"
        assert blk["bbox_preprocessed"] == [10, 10, 100, 50]
        assert blk["reading_order"] == 2
        assert fused["pages"][0]["blocks"][1] is blk

    def test_unrecognized_degrades_in_place(self):
        fused, _ = _three_block_fused()
        apply_formula_replacements(fused, {"p1_e2": {"latex": None, "formula_region_id": 1}})
        blk = _block(fused, "p1_e2")
        assert blk["processing_status"] == "formula_unrecognized"
        assert blk["payload"] == {"text": "", "confidence": 0.9}
        assert blk["block_id"] == "p1_e2"

    def test_no_hit_keeps_placeholder(self):
        fused, _ = _three_block_fused()
        apply_formula_replacements(fused, {})
        assert _block(fused, "p1_e2")["processing_status"] == "skip_formula"

    def test_all_pages_swapped(self):
        elements = [
            _elem("p1_e1", "formula", page=1, text=""),
            _elem("p2_e1", "formula", page=2, text=""),
        ]
        fused = builder.build_fused_layer(_layout(elements))
        apply_formula_replacements(
            fused,
            {
                "p1_e1": {"latex": "one", "formula_region_id": 1},
                "p2_e1": {"latex": "two", "formula_region_id": 1},
            },
        )
        assert _block(fused, "p1_e1")["processing_status"] == "recognized"
        assert _block(fused, "p2_e1")["processing_status"] == "recognized"
        assert _block(fused, "p2_e1")["payload"]["text"] == "$$two$$"


class TestViewAggregation:
    def test_formulas_aggregate_with_reading_order_and_content_flow(self):
        fused, _ = _three_block_fused()
        apply_formula_replacements(
            fused, {"p1_e2": {"latex": "E=mc^2", "formula_region_id": 1}}
        )
        elements_layout = _layout([
            _elem("p1_e1", "text", text="para one", order=1),
            _elem("p1_e2", "formula", text="", order=2),
            _elem("p1_e3", "text", text="para two", order=3),
        ])
        preprocessing = builder.build_preprocessing_metadata(
            elements_layout, use_doc_unwarping=False
        )
        view = builder.build_view_layer(fused, preprocessing)

        assert len(view["formulas"]) == 1
        entry = view["formulas"][0]
        assert entry["id"] == "p1_e2"
        assert entry["reading_order"] == 2
        assert entry["payload"]["latex"] == "E=mc^2"
        assert entry["processing_status"] == "recognized"
        # body-text flow: $$LaTeX$$ sits between the two paragraphs
        lines = view["pages"][0]["content"].split("\n")
        assert lines == ["para one", "$$E=mc^2$$", "para two"]

    def test_unrecognized_still_aggregates_for_pending_display(self):
        fused, _ = _three_block_fused()
        apply_formula_replacements(fused, {"p1_e2": {"latex": None, "formula_region_id": 1}})
        elements_layout = _layout([
            _elem("p1_e1", "text", text="para one", order=1),
            _elem("p1_e2", "formula", text="", order=2),
            _elem("p1_e3", "text", text="para two", order=3),
        ])
        preprocessing = builder.build_preprocessing_metadata(
            elements_layout, use_doc_unwarping=False
        )
        view = builder.build_view_layer(fused, preprocessing)
        assert len(view["formulas"]) == 1
        assert view["formulas"][0]["processing_status"] == "formula_unrecognized"
