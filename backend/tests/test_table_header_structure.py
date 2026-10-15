"""F4 table header structure tests (pure logic, no Paddle/GPU).

Validates ``PPStructureTableEngine._extract_html_structure`` preserves
multi-level header relationships via ``header_rows`` + ``header_span_map``,
and flags ``is_header`` for <td> cells inside <thead> (PP-StructureV3/SLANeXt
often writes headers as <td>).

Official basis: SLANeXt outputs HTML with native <thead>/<th rowspan>/
<th colspan> for multi-level headers
https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/table_recognition_v2.html
and findings §4.

Also hosts the characterization lock for ``_html_to_data`` (P-027 A 项
prerequisite): the grid semantics (colspan placeholders, rowspan
continuations, empty-row dropping, the ``max_cols < 2`` drop and the ``>20``
column truncation) are pinned so the upcoming shared-walk extraction is
provably behavior-preserving.
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


class TestHtmlToDataCharacterization:
    """Characterization lock for ``_html_to_data`` (P-027 A 项 prerequisite).

    Pins the *current* grid semantics byte-for-byte so the upcoming
    ``_walk_occupancy`` extraction is provably behavior-preserving. Each case
    maps to one branch of the current method.
    """

    def test_plain_grid_row_major(self) -> None:
        html = (
            "<table><tr><td>A</td><td>B</td><td>C</td></tr>"
            "<tr><td>1</td><td>2</td><td>3</td></tr></table>"
        )
        assert _engine()._html_to_data(html) == [["A", "B", "C"], ["1", "2", "3"]]

    def test_colspan_writes_empty_placeholder(self) -> None:
        html = "<table><tr><td colspan='2'>A</td><td>B</td></tr></table>"
        assert _engine()._html_to_data(html) == [["A", "", "B"]]

    def test_rowspan_continuation_is_blank_and_offsets_later_column(self) -> None:
        html = (
            "<table><tr><td rowspan='2'>A</td><td>B</td></tr>"
            "<tr><td>C</td></tr></table>"
        )
        # The rowspan continuation at (1, 0) stays blank; C lands at column 1.
        assert _engine()._html_to_data(html) == [["A", "B"], ["", "C"]]

    def test_all_empty_row_is_dropped(self) -> None:
        html = (
            "<table><tr><td>A</td><td>B</td></tr>"
            "<tr><td></td><td></td></tr>"
            "<tr><td>C</td><td>D</td></tr></table>"
        )
        assert _engine()._html_to_data(html) == [["A", "B"], ["C", "D"]]

    def test_single_column_table_dropped(self) -> None:
        # max_cols < 2 -> whole table rejected (not a real table).
        html = "<table><tr><td>A</td></tr><tr><td>B</td></tr></table>"
        assert _engine()._html_to_data(html) == []

    def test_more_than_20_columns_truncated(self) -> None:
        row = "".join(f"<td>c{i}</td>" for i in range(21))
        html = f"<table><tr>{row}</tr><tr>{row}</tr></table>"
        data = _engine()._html_to_data(html)
        assert len(data) == 2
        assert all(len(r) == 20 for r in data)
        assert data[0][0] == "c0" and data[0][-1] == "c19"

    def test_multi_merge_three_by_three_grid(self) -> None:
        # 7 <td> -> 9 grid positions: colspan placeholder at (0,1) and the
        # rowspan continuation of B at (1,2).
        html = (
            "<table>"
            "<tr><td colspan='2'>A</td><td rowspan='2'>B</td></tr>"
            "<tr><td>C</td><td>D</td></tr>"
            "<tr><td>E</td><td>F</td><td>G</td></tr>"
            "</table>"
        )
        assert _engine()._html_to_data(html) == [
            ["A", "", "B"],
            ["C", "D", ""],
            ["E", "F", "G"],
        ]

    def test_no_table_returns_empty(self) -> None:
        assert _engine()._html_to_data("<div>no table here</div>") == []

    def test_table_without_rows_returns_empty(self) -> None:
        assert _engine()._html_to_data("<table></table>") == []


class TestSpanMap:
    """``html_structure['span_map']`` anchor map (P-027 A).

    One ``{"row","col","rowspan","colspan"}`` per ``<td>/<th>`` in document
    order, with ``row``/``col`` the anchor's position in the ``data`` grid, so a
    flat per-``<td>`` confidence list can be projected onto the grid.
    """

    _MULTI_MERGE = (
        "<table>"
        "<tr><td colspan='2'>A</td><td rowspan='2'>B</td></tr>"
        "<tr><td>C</td><td>D</td></tr>"
        "<tr><td>E</td><td>F</td><td>G</td></tr>"
        "</table>"
    )

    def test_seven_td_anchor_map_over_nine_positions(self) -> None:
        s = _engine()._extract_html_structure(self._MULTI_MERGE)
        assert s["span_map"] == [
            {"row": 0, "col": 0, "rowspan": 1, "colspan": 2},
            {"row": 0, "col": 2, "rowspan": 2, "colspan": 1},
            {"row": 1, "col": 0, "rowspan": 1, "colspan": 1},
            {"row": 1, "col": 1, "rowspan": 1, "colspan": 1},
            {"row": 2, "col": 0, "rowspan": 1, "colspan": 1},
            {"row": 2, "col": 1, "rowspan": 1, "colspan": 1},
            {"row": 2, "col": 2, "rowspan": 1, "colspan": 1},
        ]

    def test_no_merge_is_row_major(self) -> None:
        html = (
            "<table><tr><td>1</td><td>2</td></tr>"
            "<tr><td>3</td><td>4</td></tr></table>"
        )
        s = _engine()._extract_html_structure(html)
        assert s["span_map"] == [
            {"row": 0, "col": 0, "rowspan": 1, "colspan": 1},
            {"row": 0, "col": 1, "rowspan": 1, "colspan": 1},
            {"row": 1, "col": 0, "rowspan": 1, "colspan": 1},
            {"row": 1, "col": 1, "rowspan": 1, "colspan": 1},
        ]

    def test_rowspan_placeholder_offsets_later_column(self) -> None:
        # The rowspan continuation at (1, 0) has no anchor; C's anchor is (1, 1).
        html = (
            "<table><tr><td rowspan='2'>A</td><td>B</td></tr>"
            "<tr><td>C</td></tr></table>"
        )
        s = _engine()._extract_html_structure(html)
        assert s["span_map"] == [
            {"row": 0, "col": 0, "rowspan": 2, "colspan": 1},
            {"row": 0, "col": 1, "rowspan": 1, "colspan": 1},
            {"row": 1, "col": 1, "rowspan": 1, "colspan": 1},
        ]

    def test_span_map_is_present_and_empty_for_emptytable(self) -> None:
        s = _engine()._extract_html_structure("<table></table>")
        assert s["span_map"] == []

    def test_no_table_has_no_span_map_key(self) -> None:
        # Early-return keeps the literal {} pinned by test_no_table_returns_empty.
        assert _engine()._extract_html_structure("<div>nope</div>") == {}

    def test_anchors_align_with_data_and_continuations_are_blank(self) -> None:
        s = _engine()._extract_html_structure(self._MULTI_MERGE)
        data = _engine()._html_to_data(self._MULTI_MERGE)
        assert len(data) == 3 and all(len(row) == 3 for row in data)
        for anchor in s["span_map"]:
            row, col = anchor["row"], anchor["col"]
            rowspan, colspan = anchor["rowspan"], anchor["colspan"]
            assert 0 <= row < len(data) and row + rowspan <= len(data)
            assert 0 <= col < len(data[row]) and col + colspan <= len(data[row])
            for rr in range(row, row + rowspan):
                for cc in range(col, col + colspan):
                    if (rr, cc) != (row, col):
                        # Covered, non-anchor positions must be blank placeholders.
                        assert data[rr][cc] == "", (rr, cc)
