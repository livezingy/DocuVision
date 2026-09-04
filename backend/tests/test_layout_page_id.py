"""Layout element id page-prefix tests (pure logic, no Paddle/GPU).

Validates that ``PPStructureEngine._parse_result`` stamps element ids with
the real page number (``p{page_num}_e{n}``) so multi-page PDFs produce
globally-unique ids instead of every page reusing ``p1_e*`` which caused
crop-file overwrites in figure_service.

See plan: pp-structurev3_layout-first 修复 §修改2.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

import pytest

_LAYOUT_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "layout_service.py"
_spec = importlib.util.spec_from_file_location("layout_service_for_tests", _LAYOUT_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
PPStructureEngine = _mod.PPStructureEngine


def _engine():
    # Bypass __init__ (which would lazy-init PPStructureV3). We only call the
    # pure _parse_result method.
    eng = PPStructureEngine.__new__(PPStructureEngine)
    return eng


def _mock_result(label: str, bbox: List[float], content: str = "", block_order: int = 0) -> List[Dict[str, Any]]:
    """Build a minimal parsing_res_list-style result that _parse_result accepts.

    The real LayoutParsingResultV2 exposes dict keys; we mirror the dict shape
    so the 'parsing_res_list' fast-path is taken.
    """
    return [
        {
            "parsing_res_list": [
                {
                    "label": label,
                    "bbox": bbox,
                    "content": content,
                    "index": 0,
                    "block_order": block_order,
                }
            ],
            "table_res_list": [],
            "layout_det_res": {"boxes": []},
        }
    ]


class TestParseResultPageId:
    def test_id_carries_page_number(self):
        """Element id must be p{page_num}_e{n}, not hardcoded p1."""
        eng = _engine()
        for page_num in (1, 5, 18, 36):
            result = _mock_result("text", [100, 100, 200, 200], content="hello", block_order=0)
            elements = eng._parse_result(result, page_num)
            assert len(elements) == 1
            el = elements[0]
            assert el["id"] == f"p{page_num}_e0", (
                f"page {page_num}: id should be p{page_num}_e0, got {el['id']}"
            )
            assert el["page"] == page_num

    def test_different_pages_produce_unique_ids(self):
        """Two pages with the same block index must produce different ids."""
        eng = _engine()
        ids = set()
        for page_num in (1, 2, 3):
            result = _mock_result("text", [100, 100, 200, 200], content="x", block_order=0)
            elements = eng._parse_result(result, page_num)
            ids.add(elements[0]["id"])
        assert len(ids) == 3, f"ids across pages must be unique, got {ids}"
        assert "p1_e0" in ids
        assert "p2_e0" in ids
        assert "p3_e0" in ids

    def test_table_element_gets_page_id(self):
        """Table elements also carry the page-prefixed id."""
        eng = _engine()
        result = _mock_result("table", [100, 100, 500, 300], content="", block_order=0)
        # Add table html so the table branch is exercised.
        result[0]["table_res_list"] = [
            {"table_region_id": 0, "pred_html": "<table><tr><td>a</td></tr></table>"}
        ]
        elements = eng._parse_result(result, 7)
        assert len(elements) == 1
        assert elements[0]["id"] == "p7_e0"
        assert elements[0]["page"] == 7
