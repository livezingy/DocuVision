"""Pseudo-table filter + caption strip tests (pure logic, no Paddle/GPU).

Validates ``PPStructureTableEngine._extract_from_layout_elements`` drops
empty/tiny (<3x3) pseudo-tables that PP-DocLayout may mis-detect (header
rules, axis lines), and strips a leading "Table N:" / "Figure N:" caption
row that SLANeXt occasionally includes as the first table row.

See plan: pp-structurev3_layout-first 修复 §修改4.
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
    # pure _extract_from_layout_elements method.
    eng = PPStructureTableEngine.__new__(PPStructureTableEngine)
    return eng


def _table_elem(elem_id: str, page: int, html: str, bbox=None):
    return {
        "id": elem_id,
        "page": page,
        "type": "table",
        "bbox": bbox or {"x": 100, "y": 100, "width": 400, "height": 200},
        "confidence": 0.9,
        "html": html,
    }


class TestPseudoTableFilter:
    def test_empty_table_dropped(self):
        """A 2x2 table with all empty cells is a pseudo-table (header rule)."""
        html = "<table><tr><td></td><td></td></tr><tr><td></td><td></td></tr></table>"
        elements = [_table_elem("p1_e0", 1, html)]
        tables = _engine()._extract_from_layout_elements(elements)
        assert tables == [], "empty 2x2 pseudo-table should be dropped"

    def test_tiny_table_dropped(self):
        """A 2x2 table with some content but <3 rows and <3 cols is too small."""
        html = "<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>"
        elements = [_table_elem("p1_e0", 1, html)]
        tables = _engine()._extract_from_layout_elements(elements)
        assert tables == [], "tiny 2x2 pseudo-table should be dropped"

    def test_real_table_kept(self):
        """A 3x3+ table with content is kept."""
        html = (
            "<table><tr><td>H1</td><td>H2</td><td>H3</td></tr>"
            "<tr><td>1</td><td>2</td><td>3</td></tr>"
            "<tr><td>4</td><td>5</td><td>6</td></tr></table>"
        )
        elements = [_table_elem("p1_e0", 1, html)]
        tables = _engine()._extract_from_layout_elements(elements)
        assert len(tables) == 1, "real 3x3 table should be kept"


class TestCaptionStrip:
    def test_table_caption_stripped(self):
        """A leading 'Table 1:' row (single spanned cell) is stripped to caption."""
        html = (
            "<table><tr><td colspan='3'>Table 1: Ablation results</td></tr>"
            "<tr><td>H1</td><td>H2</td><td>H3</td></tr>"
            "<tr><td>1</td><td>2</td><td>3</td></tr></table>"
        )
        elements = [_table_elem("p1_e0", 1, html)]
        tables = _engine()._extract_from_layout_elements(elements)
        assert len(tables) == 1
        tbl = tables[0]
        assert "caption" in tbl
        assert "Table 1:" in tbl["caption"]
        # Caption row stripped from data.
        assert len(tbl["data"]) == 2, "caption row should be stripped from data"

    def test_figure_caption_stripped(self):
        """A leading 'Figure 2:' row is also stripped."""
        html = (
            "<table><tr><td colspan='2'>Figure 2: Architecture diagram</td></tr>"
            "<tr><td>a</td><td>b</td></tr>"
            "<tr><td>c</td><td>d</td></tr>"
            "<tr><td>e</td><td>f</td></tr></table>"
        )
        elements = [_table_elem("p1_e0", 1, html)]
        tables = _engine()._extract_from_layout_elements(elements)
        assert len(tables) == 1
        tbl = tables[0]
        assert "Figure 2:" in tbl.get("caption", "")
        assert len(tbl["data"]) == 3, "caption row stripped, 3 data rows remain"

    def test_real_header_not_stripped(self):
        """A 3-cell header row that does not match caption pattern is kept."""
        html = (
            "<table><tr><th>H1</th><th>H2</th><th>H3</th></tr>"
            "<tr><td>1</td><td>2</td><td>3</td></tr>"
            "<tr><td>4</td><td>5</td><td>6</td></tr></table>"
        )
        elements = [_table_elem("p1_e0", 1, html)]
        tables = _engine()._extract_from_layout_elements(elements)
        assert len(tables) == 1
        tbl = tables[0]
        # No caption stripped (header row is not a caption).
        assert tbl.get("caption", "") == "" or "Table" not in tbl.get("caption", "")
        assert len(tbl["data"]) == 3, "all 3 rows kept when no caption pattern"
