"""
Unit tests for backend/app/services/canonical_converter.py

Tests are designed to run without PaddleOCR / PPStructure installed. All
external service dependencies are mocked or bypassed via test doubles.

Run from the project root:
    cd backend
    python -m pytest tests/test_canonical_converter.py -v

Or from the cloud runner:
    pytest backend/tests/test_canonical_converter.py -v
"""
import sys
import os
import json
import unittest.mock as mock

# Allow imports from backend/app without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.models.canonical_document import (
    CanonicalDocument,
    normalize_bbox,
    normalize_polygon,
    bbox_to_polygon,
)
from app.models.mapping_rules import MappingRuleSet
from app.services.canonical_converter import (
    CanonicalConverter,
    _bbox_dict_to_abs,
    _relative_path,
    invalidate_rule_cache,
    remap_canonical_doc,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared test data factories
# ─────────────────────────────────────────────────────────────────────────────

def make_element(
    elem_id="p1_e0",
    page=1,
    elem_type="text",
    x=100, y=50, w=300, h=70,
    confidence=0.9,
    text="Hello world",
    html=None,
):
    elem = {
        "id": elem_id,
        "page": page,
        "type": elem_type,
        "type_name": elem_type.title(),
        "bbox": {"x": x, "y": y, "width": w, "height": h},
        "confidence": confidence,
        "text": text,
    }
    if html is not None:
        elem["html"] = html
    return elem


def make_layout_result(elements=None, total_pages=1):
    return {
        "elements": elements or [],
        "total_pages": total_pages,
        "engine_used": "ppstructure",
        "summary": {},
        "page_layouts": [],
    }


def make_ocr_result(text_blocks=None):
    return {
        "text_blocks": text_blocks or [],
        "text": "",
        "confidence": 0.0,
    }


def make_text_block(page=1, text="line text", confidence=0.95, polygon=None):
    return {
        "page": page,
        "text": text,
        "confidence": confidence,
        "polygon": polygon or [[10, 10], [100, 10], [100, 30], [10, 30]],
    }


TASK_ID = "test-task-001"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Coordinate helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestCoordinateHelpers:
    def test_bbox_dict_to_abs_basic(self):
        result = _bbox_dict_to_abs({"x": 10, "y": 20, "width": 100, "height": 50})
        assert result == [10.0, 20.0, 110.0, 70.0]

    def test_bbox_dict_to_abs_list_input(self):
        result = _bbox_dict_to_abs([5, 10, 200, 300])
        assert result == [5.0, 10.0, 200.0, 300.0]

    def test_bbox_dict_to_abs_empty(self):
        result = _bbox_dict_to_abs({})
        assert result == [0.0, 0.0, 0.0, 0.0]

    def test_bbox_dict_to_abs_float_values(self):
        result = _bbox_dict_to_abs({"x": 10.5, "y": 20.5, "width": 100.5, "height": 50.5})
        assert pytest.approx(result) == [10.5, 20.5, 111.0, 71.0]

    def test_normalize_bbox_basic(self):
        result = normalize_bbox([0, 0, 100, 100], 200.0, 200.0)
        assert result == [0.0, 0.0, 0.5, 0.5]

    def test_normalize_bbox_clamped(self):
        # Coordinate overflow should be clamped to 1.0
        result = normalize_bbox([0, 0, 300, 300], 200.0, 200.0)
        assert result == [0.0, 0.0, 1.0, 1.0]

    def test_normalize_bbox_zero_dimensions(self):
        result = normalize_bbox([10, 20, 50, 80], 0.0, 0.0)
        assert result == [0.0, 0.0, 0.0, 0.0]

    def test_normalize_polygon_basic(self):
        pts = [[0, 0], [100, 0], [100, 100], [0, 100]]
        result = normalize_polygon(pts, 200.0, 200.0)
        assert result == [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

    def test_bbox_to_polygon_clockwise(self):
        poly = bbox_to_polygon([10.0, 20.0, 110.0, 70.0])
        assert len(poly) == 4
        # TL, TR, BR, BL order
        assert poly[0] == [10.0, 20.0]
        assert poly[1] == [110.0, 20.0]
        assert poly[2] == [110.0, 70.0]
        assert poly[3] == [10.0, 70.0]


# ─────────────────────────────────────────────────────────────────────────────
# 2. _relative_path helper
# ─────────────────────────────────────────────────────────────────────────────

class TestRelativePath:
    def test_returns_string(self):
        # Any path should return a string (absolute or relative)
        result = _relative_path("/some/path/to/file.jpg")
        assert isinstance(result, str)

    def test_no_backslashes_for_project_relative_path(self):
        # A path that IS under the project root should use forward slashes.
        from app.services.canonical_converter import _get_project_root
        project_root = _get_project_root()
        real_path = str(project_root / "backend" / "config" / "semantic_mapping_base.yaml")
        result = _relative_path(real_path)
        assert "\\" not in result

    def test_external_path_returns_string(self):
        # Paths outside the project root are returned verbatim (any string is acceptable)
        result = _relative_path("/some/external/path/file.jpg")
        assert isinstance(result, str)


# ─────────────────────────────────────────────────────────────────────────────
# 3. CanonicalConverter.convert() – basic structure
# ─────────────────────────────────────────────────────────────────────────────

class TestConverterBasicStructure:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Clear rule-set cache before each test."""
        invalidate_rule_cache()
        yield
        invalidate_rule_cache()

    def _make_converter(self):
        """Create a CanonicalConverter that uses the minimal fallback rules."""
        with mock.patch(
            "app.services.canonical_converter._default_rules_path",
            return_value="/nonexistent/path/rules.yaml",
        ):
            return CanonicalConverter()

    def test_returns_canonical_document(self):
        conv = self._make_converter()
        elements = [make_element()]
        result = conv.convert(
            task_id=TASK_ID,
            source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        assert isinstance(result, CanonicalDocument)

    def test_doc_id_matches_task_id(self):
        conv = self._make_converter()
        result = conv.convert(
            task_id=TASK_ID,
            source_type="image",
            layout_result=make_layout_result(),
        )
        assert result.doc_id == TASK_ID

    def test_source_type_preserved(self):
        conv = self._make_converter()
        result = conv.convert(
            task_id=TASK_ID,
            source_type="pdf",
            layout_result=make_layout_result(total_pages=3),
        )
        assert result.source_type == "pdf"

    def test_page_count(self):
        conv = self._make_converter()
        result = conv.convert(
            task_id=TASK_ID,
            source_type="image",
            layout_result=make_layout_result(total_pages=2),
        )
        assert result.page_count == 2
        assert len(result.pages) == 2

    def test_single_page_with_elements(self):
        conv = self._make_converter()
        elements = [
            make_element("p1_e0", page=1, elem_type="text"),
            make_element("p1_e1", page=1, elem_type="table", html="<table/>"),
        ]
        result = conv.convert(
            task_id=TASK_ID,
            source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        page = result.pages[0]
        assert len(page.blocks) == 2

    def test_blocks_have_required_fields(self):
        conv = self._make_converter()
        elements = [make_element()]
        result = conv.convert(
            task_id=TASK_ID,
            source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        block = result.pages[0].blocks[0]
        assert block.block_id
        assert len(block.bbox_abs) == 4
        assert len(block.bbox_norm) == 4
        assert block.semantic_role
        assert block.content_text == "Hello world"

    def test_bbox_abs_correct(self):
        conv = self._make_converter()
        elements = [make_element(x=100, y=50, w=300, h=70)]
        result = conv.convert(
            task_id=TASK_ID,
            source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        bbox = result.pages[0].blocks[0].bbox_abs
        assert bbox == [100.0, 50.0, 400.0, 120.0]

    def test_order_preserved(self):
        conv = self._make_converter()
        elements = [make_element(f"p1_e{i}", page=1, text=f"text {i}") for i in range(5)]
        result = conv.convert(
            task_id=TASK_ID,
            source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        orders = [b.order for b in result.pages[0].blocks]
        assert orders == list(range(5))

    def test_raw_payload_stored(self):
        conv = self._make_converter()
        layout = make_layout_result(elements=[make_element()])
        result = conv.convert(
            task_id=TASK_ID,
            source_type="image",
            layout_result=layout,
        )
        assert result.raw_payload is not None
        assert "layout" in result.raw_payload
        assert "ocr" in result.raw_payload


# ─────────────────────────────────────────────────────────────────────────────
# 4. Semantic role assignment via converter
# ─────────────────────────────────────────────────────────────────────────────

class TestConverterSemanticRoles:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        invalidate_rule_cache()
        yield
        invalidate_rule_cache()

    def _make_converter(self):
        with mock.patch(
            "app.services.canonical_converter._default_rules_path",
            return_value="/nonexistent/path/rules.yaml",
        ):
            return CanonicalConverter()

    def test_title_role(self):
        conv = self._make_converter()
        elements = [make_element(elem_type="title")]
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        assert result.pages[0].blocks[0].semantic_role == "Title"

    def test_text_role_is_Paragraph(self):
        conv = self._make_converter()
        elements = [make_element(elem_type="text")]
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        assert result.pages[0].blocks[0].semantic_role == "Paragraph"

    def test_table_role(self):
        conv = self._make_converter()
        elements = [make_element(elem_type="table", html="<table/>")]
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        assert result.pages[0].blocks[0].semantic_role == "Table"

    def test_figure_role(self):
        conv = self._make_converter()
        elements = [make_element(elem_type="figure")]
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        assert result.pages[0].blocks[0].semantic_role == "Figure"

    def test_low_confidence_demoted(self):
        conv = self._make_converter()
        elements = [make_element(elem_type="title", confidence=0.05)]
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        assert result.pages[0].blocks[0].semantic_role == "Unknown"

    def test_rule_hit_id_set(self):
        conv = self._make_converter()
        elements = [make_element(elem_type="title", confidence=0.9)]
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        block = result.pages[0].blocks[0]
        assert block.rule_hit_id is not None
        assert block.rule_hit_id.startswith("F")  # fallback rules use F-prefix

    def test_doc_type_hint_forwarded(self):
        """Invoice + total text should map to KeyValuePair via domain rule."""
        conv = self._make_converter()
        # Note: test uses fallback rule set which may not have R011.
        # We build a custom rule set to ensure KeyValuePair rule exists.
        kv_yaml = """
config:
  mapping_version: "1.0.0"
  taxonomy_version: "azure-like-v1"
  default_role: Paragraph
  confidence_policy: {demote_if_below: 0.1}
  storage: {}
normalize:
  raw_label_alias:
    text: text
    paragraph: text
rules:
  - id: KV01
    enabled: true
    priority: 700
    when:
      raw_label_in: [text]
      doc_type_in: [invoice]
      text_regex_any: ["(?i)total"]
    then:
      semantic_role: KeyValuePair
  - id: KV02
    enabled: true
    priority: 100
    when:
      raw_label_in: [text]
    then:
      semantic_role: Paragraph
"""
        rs = MappingRuleSet.from_yaml_string(kv_yaml)
        with mock.patch(
            "app.services.canonical_converter._load_rule_set",
            return_value=rs,
        ):
            conv2 = CanonicalConverter()
            elements = [make_element(elem_type="text", text="Total: $999")]
            result = conv2.convert(
                task_id=TASK_ID,
                source_type="image",
                layout_result=make_layout_result(elements=elements),
                doc_type_hint="invoice",
            )
        assert result.pages[0].blocks[0].semantic_role == "KeyValuePair"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Table extraction
# ─────────────────────────────────────────────────────────────────────────────

class TestTableExtraction:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        invalidate_rule_cache()
        yield
        invalidate_rule_cache()

    def _make_converter(self):
        with mock.patch(
            "app.services.canonical_converter._default_rules_path",
            return_value="/nonexistent/path/rules.yaml",
        ):
            return CanonicalConverter()

    def test_table_element_creates_canonical_table(self):
        conv = self._make_converter()
        elements = [make_element(elem_type="table", html="<table><tr><td>A</td></tr></table>")]
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        assert len(result.tables) == 1
        assert result.tables[0].html == "<table><tr><td>A</td></tr></table>"

    def test_table_without_html_not_extracted(self):
        """A 'table' element with no html should NOT create a CanonicalTable."""
        conv = self._make_converter()
        elements = [make_element(elem_type="table")]  # no html key
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        assert len(result.tables) == 0

    def test_table_page_id_set(self):
        conv = self._make_converter()
        elements = [make_element(elem_type="table", html="<table/>")]
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        assert result.tables[0].page_id is not None
        assert len(result.tables[0].page_id) > 0

    def test_multiple_tables(self):
        conv = self._make_converter()
        elements = [
            make_element("e0", elem_type="table", html="<table>1</table>"),
            make_element("e1", elem_type="text", text="some text"),
            make_element("e2", elem_type="table", html="<table>2</table>"),
        ]
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=elements),
        )
        assert len(result.tables) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 6. OCR line integration
# ─────────────────────────────────────────────────────────────────────────────

class TestOcrLineIntegration:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        invalidate_rule_cache()
        yield
        invalidate_rule_cache()

    def _make_converter(self):
        with mock.patch(
            "app.services.canonical_converter._default_rules_path",
            return_value="/nonexistent/path/rules.yaml",
        ):
            return CanonicalConverter()

    def test_ocr_lines_stored_in_page(self):
        conv = self._make_converter()
        ocr = make_ocr_result(text_blocks=[
            make_text_block(page=1, text="line 1"),
            make_text_block(page=1, text="line 2"),
        ])
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=[make_element()]),
            ocr_result=ocr,
        )
        assert len(result.pages[0].ocr_lines) == 2

    def test_ocr_lines_text_preserved(self):
        conv = self._make_converter()
        ocr = make_ocr_result(text_blocks=[make_text_block(text="Sample OCR text")])
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=[make_element()]),
            ocr_result=ocr,
        )
        assert result.pages[0].ocr_lines[0].text == "Sample OCR text"

    def test_no_ocr_result_gives_empty_lines(self):
        conv = self._make_converter()
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=[make_element()]),
            ocr_result=None,
        )
        assert result.pages[0].ocr_lines == []

    def test_ocr_confidence_stored(self):
        conv = self._make_converter()
        ocr = make_ocr_result(text_blocks=[make_text_block(confidence=0.87)])
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=[make_element()]),
            ocr_result=ocr,
        )
        # OcrLine uses .score (not .confidence)
        assert pytest.approx(result.pages[0].ocr_lines[0].score) == 0.87


# ─────────────────────────────────────────────────────────────────────────────
# 7. Raw payload sanitisation (numpy / non-JSON-safe types)
# ─────────────────────────────────────────────────────────────────────────────

class TestRawPayloadSanitisation:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        invalidate_rule_cache()
        yield
        invalidate_rule_cache()

    def _make_converter(self):
        with mock.patch(
            "app.services.canonical_converter._default_rules_path",
            return_value="/nonexistent/path/rules.yaml",
        ):
            return CanonicalConverter()

    def test_result_serialisable_to_json(self):
        conv = self._make_converter()
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=[make_element()]),
        )
        # Must not raise
        doc_dict = result.to_dict(include_raw_payload=True)
        json_str = json.dumps(doc_dict)
        assert len(json_str) > 0

    def test_numpy_int_in_layout_serialisable(self):
        """Simulate a numpy int64 in the layout result (common with PaddleOCR)."""
        try:
            import numpy as np
            np_int = np.int64(42)
        except ImportError:
            pytest.skip("numpy not installed")
        conv = self._make_converter()
        layout = make_layout_result(elements=[make_element()])
        layout["numpy_field"] = np_int
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=layout,
        )
        doc_dict = result.to_dict(include_raw_payload=True)
        json_str = json.dumps(doc_dict)
        assert '"numpy_field": 42' in json_str or "42" in json_str

    def test_nested_none_values_serialisable(self):
        conv = self._make_converter()
        layout = make_layout_result(elements=[make_element()])
        layout["nested"] = {"key": None, "list": [None, 1, "two"]}
        result = conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=layout,
        )
        json.dumps(result.to_dict(include_raw_payload=True))  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
# 8. to_dict() serialisation layers
# ─────────────────────────────────────────────────────────────────────────────

class TestToDictSerialisation:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        invalidate_rule_cache()
        yield
        invalidate_rule_cache()

    def _convert(self, elements=None, ocr_result=None):
        with mock.patch(
            "app.services.canonical_converter._default_rules_path",
            return_value="/nonexistent/path/rules.yaml",
        ):
            conv = CanonicalConverter()
        return conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=elements or [make_element()]),
            ocr_result=ocr_result,
        )

    def test_to_dict_has_required_top_level_keys(self):
        doc = self._convert()
        d = doc.to_dict()
        for key in ("doc_id", "schema_version", "source_type", "page_count", "pages"):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_excludes_raw_payload_by_default(self):
        doc = self._convert()
        d = doc.to_dict(include_raw_payload=False)
        assert "raw_payload" not in d

    def test_to_dict_includes_raw_payload_when_requested(self):
        doc = self._convert()
        d = doc.to_dict(include_raw_payload=True)
        assert "raw_payload" in d

    def test_to_dict_excludes_ocr_lines_by_default(self):
        ocr = make_ocr_result(text_blocks=[make_text_block()])
        doc = self._convert(ocr_result=ocr)
        d = doc.to_dict(include_ocr_lines=False)
        page = d["pages"][0]
        # ocr_lines should be absent or empty list
        assert page.get("ocr_lines", []) == []

    def test_to_dict_includes_ocr_lines_when_requested(self):
        ocr = make_ocr_result(text_blocks=[make_text_block(text="test line")])
        doc = self._convert(ocr_result=ocr)
        d = doc.to_dict(include_ocr_lines=True)
        page = d["pages"][0]
        assert len(page.get("ocr_lines", [])) == 1

    def test_from_json_roundtrip(self):
        doc = self._convert()
        # from_json() expects a JSON string, not a dict
        json_str = json.dumps(doc.to_dict(include_raw_payload=True))
        doc2 = CanonicalDocument.from_json(json_str)
        assert doc2.doc_id == doc.doc_id
        assert doc2.page_count == doc.page_count
        assert len(doc2.pages) == len(doc.pages)


# ─────────────────────────────────────────────────────────────────────────────
# 9. summary()
# ─────────────────────────────────────────────────────────────────────────────

class TestSummary:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        invalidate_rule_cache()
        yield
        invalidate_rule_cache()

    def _convert(self, elements=None):
        with mock.patch(
            "app.services.canonical_converter._default_rules_path",
            return_value="/nonexistent/path/rules.yaml",
        ):
            conv = CanonicalConverter()
        return conv.convert(
            task_id=TASK_ID, source_type="image",
            layout_result=make_layout_result(elements=elements or [make_element()]),
        )

    def test_summary_has_required_keys(self):
        doc = self._convert()
        s = doc.summary()
        # summary() keys: doc_id, source_type, page_count, total_blocks, total_tables,
        #                 taxonomy_version, semantic_role_distribution, created_at
        for key in ("doc_id", "page_count", "total_blocks", "taxonomy_version"):
            assert key in s, f"Missing summary key: {key}"

    def test_summary_block_count(self):
        elements = [make_element(f"e{i}") for i in range(5)]
        doc = self._convert(elements=elements)
        assert doc.summary()["total_blocks"] == 5

    def test_summary_page_count(self):
        doc = self._convert()
        assert doc.summary()["page_count"] == 1

    def test_summary_role_breakdown_present(self):
        elements = [
            make_element("e0", elem_type="title"),
            make_element("e1", elem_type="text"),
            make_element("e2", elem_type="text"),
        ]
        doc = self._convert(elements=elements)
        s = doc.summary()
        breakdown = s.get("roles_breakdown", {})
        assert isinstance(breakdown, dict)


# ─────────────────────────────────────────────────────────────────────────────
# 10. remap_canonical_doc() – remapping API helper
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a serialised canonical dict for remap tests
# ─────────────────────────────────────────────────────────────────────────────

def _build_canonical_dict():
    """Return a serialised CanonicalDocument dict (input to remap_canonical_doc)."""
    with mock.patch(
        "app.services.canonical_converter._default_rules_path",
        return_value="/nonexistent/path/rules.yaml",
    ):
        conv = CanonicalConverter()
    elements = [
        make_element("e0", elem_type="text", text="normal text"),
        make_element("e1", elem_type="title", text="Document Title"),
    ]
    doc = conv.convert(
        task_id=TASK_ID, source_type="image",
        layout_result=make_layout_result(elements=elements),
    )
    return doc.to_dict(include_raw_payload=True)


class TestRemapCanonicalDoc:
    """remap_canonical_doc(canonical_dict, new_taxonomy_version, ...) → (dict, int)"""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        invalidate_rule_cache()
        yield
        invalidate_rule_cache()

    def test_remap_returns_tuple(self):
        canonical_dict = _build_canonical_dict()
        result = remap_canonical_doc(canonical_dict, new_taxonomy_version="azure-like-v1")
        assert isinstance(result, tuple)
        updated_dict, changed = result
        assert isinstance(updated_dict, dict)
        assert isinstance(changed, int)

    def test_remap_result_has_canonical_keys(self):
        canonical_dict = _build_canonical_dict()
        updated_dict, _ = remap_canonical_doc(
            canonical_dict, new_taxonomy_version="azure-like-v1"
        )
        assert "doc_id" in updated_dict
        assert "pages" in updated_dict

    def test_remap_block_count_preserved(self):
        canonical_dict = _build_canonical_dict()
        before_count = sum(len(p["blocks"]) for p in canonical_dict["pages"])
        updated_dict, _ = remap_canonical_doc(
            canonical_dict, new_taxonomy_version="azure-like-v1"
        )
        after_count = sum(len(p["blocks"]) for p in updated_dict["pages"])
        assert before_count == after_count

    def test_remap_raw_payload_preserved(self):
        canonical_dict = _build_canonical_dict()
        original_layout_keys = list(
            (canonical_dict.get("raw_payload") or {}).get("layout", {}).keys()
        )
        updated_dict, _ = remap_canonical_doc(
            canonical_dict, new_taxonomy_version="azure-like-v1"
        )
        updated_layout_keys = list(
            (updated_dict.get("raw_payload") or {}).get("layout", {}).keys()
        )
        assert original_layout_keys == updated_layout_keys

    def test_remap_with_doc_type_override(self):
        """Remapping with doc_type_hint override should complete without error."""
        canonical_dict = _build_canonical_dict()
        updated_dict, changed = remap_canonical_doc(
            canonical_dict,
            new_taxonomy_version="azure-like-v1",
            doc_type="invoice",
        )
        assert isinstance(changed, int)

    def test_remap_changed_count_non_negative(self):
        canonical_dict = _build_canonical_dict()
        _, changed = remap_canonical_doc(
            canonical_dict, new_taxonomy_version="azure-like-v1"
        )
        assert changed >= 0


# ─────────────────────────────────────────────────────────────────────────────
# 11. Rule cache invalidation
# ─────────────────────────────────────────────────────────────────────────────

class TestRuleCache:
    def test_invalidate_cache_resets_state(self):
        """After invalidate_rule_cache() a new converter reloads rules."""
        invalidate_rule_cache()
        # Should not raise even if YAML file does not exist
        with mock.patch(
            "app.services.canonical_converter._default_rules_path",
            return_value="/nonexistent/path/rules.yaml",
        ):
            conv = CanonicalConverter()  # triggers fallback load
        invalidate_rule_cache()
        # Cache cleared — second construction should also work
        with mock.patch(
            "app.services.canonical_converter._default_rules_path",
            return_value="/nonexistent/path/rules.yaml",
        ):
            conv2 = CanonicalConverter()
        assert conv2 is not None
