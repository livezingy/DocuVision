"""
Unit tests for EnvelopeBuilder — no paddle/GPU required.

Covers Phase 2 Group A changes:
 - A1: processing_status correctness (skip_formula, skip_seal, extracted, no_ocr)
 - A2: quality layer field names + formula_count/seal_count + view layer aggregation
 - A3: provenance structure
"""
import sys
import os
import types

# Ensure backend package is importable without paddle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ---------------------------------------------------------------------------
# Build a minimal mock layout_result to feed EnvelopeBuilder
# ---------------------------------------------------------------------------

def _make_layout_result(elements):
    return {
        "elements": elements,
        "output_size": {"width": 1000, "height": 1400},
        "input_size": {"width": 1000, "height": 1400},
        "preprocessed_image_width": 1000,
        "preprocessed_image_height": 1400,
        "use_doc_orientation_classify": True,
        "angle_deg": 0.0,
    }

def _elem(eid, etype, text="hello", conf=0.9):
    return {
        "id": eid,
        "type": etype,
        "page": 1,
        "bbox": [10, 10, 100, 50],
        "polygon_preprocessed": [10, 10, 100, 10, 100, 50, 10, 50],
        "text": text,
        "confidence": conf,
    }

# Mock settings (EnvelopeBuilder only uses settings.DEBUG_MODE in cleanup)
class _FakeSettings:
    DEBUG_MODE = False
    DEBUG_OUTPUT_DIR = "backend/debug"
    DEBUG_KEEP_LAST_N = 10


# ---------------------------------------------------------------------------
# Import EnvelopeBuilder (must happen after sys.path is set)
# ---------------------------------------------------------------------------
from app.orchestration.envelope_builder import EnvelopeBuilder

SETTINGS = _FakeSettings()
builder = EnvelopeBuilder(SETTINGS)

ALL_ELEMENTS = [
    _elem("e1", "doc_title", text="Title text"),
    _elem("e2", "text", text="Paragraph text"),
    _elem("e3", "table", text=""),
    _elem("e4", "figure", text=""),
    _elem("e5", "image", text=""),
    _elem("e6", "formula", text=""),
    _elem("e7", "inline_formula", text=""),
    _elem("e8", "seal", text=""),
    _elem("e9", "stamp", text=""),
    _elem("e10", "chart", text=""),
]

LAYOUT_RESULT = _make_layout_result(ALL_ELEMENTS)
FUSED = builder.build_fused_layer(LAYOUT_RESULT)
PREPROCESSING = builder.build_preprocessing_metadata(LAYOUT_RESULT, use_doc_unwarping=False)
VIEW = builder.build_view_layer(FUSED, PREPROCESSING)
QUALITY = builder.build_quality_layer(FUSED, processing_time_ms=123)


def _block(bid):
    for page in FUSED["pages"]:
        for b in page["blocks"]:
            if b["block_id"] == bid:
                return b
    raise KeyError(bid)


# ===========================================================================
# A1: processing_status
# ===========================================================================

class TestProcessingStatus:
    def test_text_block_status(self):
        assert _block("e1")["processing_status"] == "no_ocr"
        assert _block("e2")["processing_status"] == "no_ocr"

    def test_table_block_status(self):
        assert _block("e3")["processing_status"] == "skip_table"

    def test_figure_extracted(self):
        assert _block("e4")["processing_status"] == "extracted"

    def test_image_extracted(self):
        assert _block("e5")["processing_status"] == "extracted"

    def test_chart_extracted(self):
        assert _block("e10")["processing_status"] == "extracted"

    def test_formula_skip(self):
        assert _block("e6")["processing_status"] == "skip_formula"

    def test_inline_formula_skip(self):
        assert _block("e7")["processing_status"] == "skip_formula"

    def test_seal_skip(self):
        assert _block("e8")["processing_status"] == "skip_seal"

    def test_stamp_skip(self):
        assert _block("e9")["processing_status"] == "skip_seal"

    def test_no_vision_block_status_anywhere(self):
        for page in FUSED["pages"]:
            for b in page["blocks"]:
                assert b["processing_status"] != "vision_block", (
                    f"Unexpected 'vision_block' on {b['block_id']} ({b['type']})"
                )


# ===========================================================================
# A3: provenance structure
# ===========================================================================

class TestProvenance:
    def test_text_block_has_provenance(self):
        prov = _block("e1")["provenance"]
        assert prov is not None
        assert prov["primary_source"] == "pp_structure_v3"
        assert prov["merge_strategy"] == "no_ocr"
        assert "primary_text" in prov
        assert prov["merged_at"] is None

    def test_text_block_provenance_text_matches(self):
        b = _block("e1")
        assert b["provenance"]["primary_text"] == "Title text"

    def test_table_provenance_is_null(self):
        assert _block("e3")["provenance"] is None

    def test_figure_provenance_is_null(self):
        assert _block("e4")["provenance"] is None

    def test_formula_provenance_is_null(self):
        assert _block("e6")["provenance"] is None

    def test_seal_provenance_is_null(self):
        assert _block("e8")["provenance"] is None


# ===========================================================================
# A2 part1: quality layer field names and counts
# ===========================================================================

class TestQualityLayer:
    def test_old_fields_absent(self):
        assert "text_blocks_no_match" not in QUALITY, "Legacy field 'text_blocks_no_match' must not be present"
        assert "avg_text_confidence" not in QUALITY, "Legacy field 'avg_text_confidence' must not be present"

    def test_new_fields_present(self):
        assert "text_blocks_no_ocr" in QUALITY
        assert "avg_layout_confidence" in QUALITY
        assert "formula_count" in QUALITY
        assert "seal_count" in QUALITY

    def test_text_counts(self):
        # e1=doc_title, e2=text → 2 text blocks, both no_ocr
        assert QUALITY["text_blocks_total"] == 2
        assert QUALITY["text_blocks_no_ocr"] == 2

    def test_table_count(self):
        assert QUALITY["table_blocks_total"] == 1

    def test_figure_count(self):
        # e4=figure, e5=image, e10=chart → 3 figure blocks
        assert QUALITY["figure_blocks_total"] == 3

    def test_formula_count(self):
        # e6=formula, e7=inline_formula → 2
        assert QUALITY["formula_count"] == 2

    def test_seal_count(self):
        # e8=seal, e9=stamp → 2
        assert QUALITY["seal_count"] == 2

    def test_processing_time(self):
        assert QUALITY["processing_time_ms"] == 123

    def test_avg_layout_confidence_type(self):
        assert isinstance(QUALITY["avg_layout_confidence"], float)


# ===========================================================================
# A2 part2: view layer aggregation for formulas / seals
# ===========================================================================

class TestViewLayerAggregation:
    def test_formulas_list_populated(self):
        assert len(VIEW["formulas"]) == 2, f"Expected 2 formulas, got {len(VIEW['formulas'])}"

    def test_seals_list_populated(self):
        assert len(VIEW["seals"]) == 2, f"Expected 2 seals, got {len(VIEW['seals'])}"

    def test_formula_kind(self):
        for elem in VIEW["formulas"]:
            assert elem["kind"] == "formula"

    def test_seal_kind(self):
        for elem in VIEW["seals"]:
            assert elem["kind"] == "seal"

    def test_figures_list_still_works(self):
        # figure/image/chart = 3 elements
        assert len(VIEW["figures"]) == 3

    def test_tables_list_still_works(self):
        assert len(VIEW["tables"]) == 1

    def test_paragraphs_list_still_works(self):
        # e1=title→kind "title" (not paragraph), e2=text→"paragraph"
        # Only e2 maps to "paragraph" kind
        assert len(VIEW["paragraphs"]) == 1

    def test_view_processing_status_skip_formula(self):
        for elem in VIEW["formulas"]:
            assert elem["processing_status"] == "skip_formula"

    def test_view_processing_status_skip_seal(self):
        for elem in VIEW["seals"]:
            assert elem["processing_status"] == "skip_seal"
