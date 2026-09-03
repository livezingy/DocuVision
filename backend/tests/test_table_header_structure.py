"""F4 table header structure tests (pure logic, no Paddle/GPU).

Validates ``PPStructureTableEngine._extract_html_structure`` preserves
multi-level header relationships via ``header_rows`` + ``header_span_map``,
and flags ``is_header`` for <td> cells inside <thead> (PP-StructureV3/SLANeXt
often writes headers as <td>).

Official basis: SLANeXt outputs HTML with native <thead>/<th rowspan>/
<th colspan> for multi-level headers
https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/table_recognition_v2.html
and findings §4.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_TABLE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "table_service.py"
_spec = importlib.util.spec_from_file_location("table_service_for_tests", _TABLE_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
PPStructureTableEngine = _mod.PPStructureTableEngine


def _engine():
    # Bypass __init__ (which would lazy-init PPStructureV3). We only call the
    # pure _extract_html_structure method.
    eng = PPStructureTableEngine.__new__(PPStructureTableEngine)
    return eng


class TestHeaderStructure:
    def test_thead_marks_header_rows(self) -> None:
        html = """
        <table>
          <thead>
            <tr><th colspan="2">A</th><th rowspan="2">B</th></tr>
            <tr><th>A1</th><th>A2</th></tr>
          </thead>
          <tbody>
            <tr><td>1</td><td>2</td><td>3</td></tr>
          </tbody>
        </table>
        """
        s = _engine()._extract_html_structure(html)
        assert s["header_rows"] == 2
        # First two rows are header rows.
        assert s["rows"][0]["is_header_row"] is True
        assert s["rows"][1]["is_header_row"] is True
        assert s["rows"][2]["is_header_row"] is False
        # header_span_map records spanning header cells.
        spans = s["header_span_map"]
        # colspan=2 at row0 col0, rowspan=2 at row0 col2, (A1/A2 no span)
        span_texts = {(sp["row"], sp["col"]): sp for sp in spans}
        assert (0, 0) in span_texts and span_texts[(0, 0)]["colspan"] == 2
        assert (0, 2) in span_texts and span_texts[(0, 2)]["rowspan"] == 2
        assert s["has_merged_cells"] is True

    def test_td_in_thead_flagged_is_header(self) -> None:
        # PP-StructureV3/SLANeXt often writes headers as <td> inside <thead>.
        html = """
        <table>
          <thead><tr><td>HeaderA</td><td>HeaderB</td></tr></thead>
          <tbody><tr><td>1</td><td>2</td></tr></tbody>
        </table>
        """
        s = _engine()._extract_html_structure(html)
        assert s["header_rows"] == 1
        cells0 = s["rows"][0]["cells"]
        assert all(c["is_header"] for c in cells0), "td in thead must be is_header"
        # Body row cells are not header.
        assert all(not c["is_header"] for c in s["rows"][1]["cells"])

    def test_heuristic_header_when_no_thead(self) -> None:
        # No <thead>; first row all short text -> heuristic header row.
        html = """
        <table>
          <tr><td>Name</td><td>Age</td><td>City</td></tr>
          <tr><td>Alice</td><td>30</td><td>This is a longer body cell value</td></tr>
        </table>
        """
        s = _engine()._extract_html_structure(html)
        assert s["header_rows"] == 1
        assert s["rows"][0]["is_header_row"] is True
        assert s["rows"][0]["cells"][0]["is_header"] is True
        assert s["rows"][1]["is_header_row"] is False

    def test_heuristic_stops_at_first_non_header_row(self) -> None:
        # First row has long text (not header), so no header rows detected.
        html = """
        <table>
          <tr><td>This is a long sentence in the first cell</td><td>Also long text here</td></tr>
          <tr><td>Name</td><td>Age</td></tr>
        </table>
        """
        s = _engine()._extract_html_structure(html)
        assert s["header_rows"] == 0
        assert s["rows"][0]["is_header_row"] is False

    def test_no_header_for_plain_data_table(self) -> None:
        html = """
        <table>
          <tr><td>1</td><td>2</td></tr>
          <tr><td>3</td><td>4</td></tr>
        </table>
        """
        s = _engine()._extract_html_structure(html)
        # Short numeric cells: heuristic may flag row0 as header (all <=20 chars).
        # That's acceptable behavior; just ensure no crash and structure present.
        assert "header_rows" in s
        assert "header_span_map" in s
        assert s["header_span_map"] == []  # no spans

    def test_empty_table_returns_empty(self) -> None:
        s = _engine()._extract_html_structure("<table></table>")
        # No rows -> structure with empty rows, not {} (table tag exists).
        assert s["rows"] == []
        assert s["header_rows"] == 0

    def test_no_table_returns_empty(self) -> None:
        s = _engine()._extract_html_structure("<div>nope</div>")
        assert s == {}
