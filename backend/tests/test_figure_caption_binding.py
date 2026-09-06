"""F3 caption-binding tests (pure logic, no Paddle/GPU).

Covers:
- ``figure_service._bind_captions``: binds figure_caption / figure_title
  elements to nearby figure regions by bbox adjacency.
- ``table_service.TableService._bind_table_captions``: binds table_caption
  elements to nearby table regions.

Official basis: caption binding is postprocessing built into PP-StructureV3
via ``update_vision_child_blocks`` (PaddleOCR 3.0 Report §3). This A-tier
implementation is a simplified bbox-adjacency reimplementation that avoids
changing the per-page predict call path.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.services.figure_service import (
    CAPTION_LABELS,
    FIGURE_LABELS,
    _bind_captions,
    _caption_elements,
)


def _elem(
    eid: str,
    etype: str,
    page: int,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str = "",
) -> Dict[str, Any]:
    return {
        "id": eid,
        "type": etype,
        "page": page,
        "bbox": {"x": x, "y": y, "width": w, "height": h},
        "text": text,
        "confidence": 0.9,
    }


# ---------------------------------------------------------------------------
# _bind_captions — figure caption binding
# ---------------------------------------------------------------------------

class TestBindFigureCaptions:
    def test_caption_below_figure_binds(self) -> None:
        figures = [_elem("fig1", "figure", 1, 100, 100, 400, 300)]
        captions = [_elem("cap1", "figure_caption", 1, 100, 410, 400, 30, "Fig 1: Circuit")]
        _bind_captions(figures, figures + captions)
        assert figures[0]["caption"] == "Fig 1: Circuit"
        assert figures[0]["caption_id"] == "cap1"

    def test_caption_above_figure_binds(self) -> None:
        figures = [_elem("fig1", "figure", 1, 100, 200, 400, 300)]
        captions = [_elem("cap1", "figure_title", 1, 100, 150, 400, 30, "Figure 1")]
        _bind_captions(figures, figures + captions)
        assert figures[0]["caption"] == "Figure 1"
        assert figures[0]["caption_id"] == "cap1"

    def test_far_caption_does_not_bind(self) -> None:
        """Caption more than v_gap_max_ratio * max(h) away → no bind."""
        figures = [_elem("fig1", "figure", 1, 100, 100, 400, 100)]
        captions = [_elem("cap1", "figure_caption", 1, 100, 500, 400, 30, "Far")]
        _bind_captions(figures, figures + captions)
        assert "caption" not in figures[0] or not figures[0]["caption"]

    def test_no_horizontal_overlap_does_not_bind(self) -> None:
        """Caption in a different column → no bind."""
        figures = [_elem("fig1", "figure", 1, 0, 100, 200, 300)]
        captions = [_elem("cap1", "figure_caption", 1, 600, 110, 200, 30, "Other col")]
        _bind_captions(figures, figures + captions)
        assert not figures[0].get("caption")

    def test_different_page_does_not_bind(self) -> None:
        figures = [_elem("fig1", "figure", 1, 100, 100, 400, 300)]
        captions = [_elem("cap1", "figure_caption", 2, 100, 110, 400, 30, "Next page")]
        _bind_captions(figures, figures + captions)
        assert not figures[0].get("caption")

    def test_closest_caption_wins(self) -> None:
        figures = [_elem("fig1", "figure", 1, 100, 100, 400, 300)]
        # figure bottom = 400
        captions = [
            _elem("cap_far", "figure_caption", 1, 100, 600, 400, 30, "Far"),  # gap = 200
            _elem("cap_near", "figure_caption", 1, 100, 405, 400, 30, "Near"),  # gap = 5
        ]
        _bind_captions(figures, figures + captions)
        assert figures[0]["caption"] == "Near"
        assert figures[0]["caption_id"] == "cap_near"

    def test_caption_consumed_once(self) -> None:
        """One caption cannot bind to two figures."""
        figures = [
            _elem("fig1", "figure", 1, 100, 100, 200, 300),
            _elem("fig2", "figure", 1, 350, 100, 200, 300),
        ]
        captions = [_elem("cap1", "figure_caption", 1, 100, 410, 200, 30, "Only one")]
        _bind_captions(figures, figures + captions)
        assert figures[0]["caption"] == "Only one"
        assert not figures[1].get("caption")

    def test_no_captions_is_noop(self) -> None:
        figures = [_elem("fig1", "figure", 1, 100, 100, 400, 300)]
        _bind_captions(figures, figures)
        assert "caption" not in figures[0]

    def test_no_figures_is_noop(self) -> None:
        captions = [_elem("cap1", "figure_caption", 1, 100, 100, 400, 30, "Orphan")]
        _bind_captions([], captions)  # must not raise

    def test_figure_table_chart_title_binds(self) -> None:
        figures = [_elem("fig1", "chart", 1, 100, 100, 400, 300)]
        captions = [_elem("cap1", "figure_table_chart_title", 1, 100, 410, 400, 30, "Chart 1")]
        _bind_captions(figures, figures + captions)
        assert figures[0]["caption"] == "Chart 1"


# ---------------------------------------------------------------------------
# _caption_elements + label coverage
# ---------------------------------------------------------------------------

class TestCaptionLabels:
    def test_expected_labels_included(self) -> None:
        for label in ("figure_caption", "figure_title", "figure_table_chart_title"):
            assert label in CAPTION_LABELS

    def test_figure_labels_separate_from_caption_labels(self) -> None:
        assert CAPTION_LABELS.isdisjoint(FIGURE_LABELS)

    def test_caption_elements_filters(self) -> None:
        elements = [
            _elem("f1", "figure", 1, 0, 0, 10, 10),
            _elem("c1", "figure_caption", 1, 0, 20, 10, 5, "Cap"),
            _elem("t1", "text", 1, 0, 30, 10, 5),
        ]
        caps = _caption_elements(elements)
        assert len(caps) == 1
        assert caps[0]["id"] == "c1"


# ---------------------------------------------------------------------------
# Table caption binding
# ---------------------------------------------------------------------------

class TestBindTableCaptions:
    def test_table_caption_binds(self) -> None:
        from app.services.table_service import PPStructureTableEngine

        tables = [{"id": "t1", "page": 1, "bbox": {"x": 100, "y": 100, "width": 400, "height": 300}}]
        elements = [
            {"id": "t1", "type": "table", "page": 1, "bbox": {"x": 100, "y": 100, "width": 400, "height": 300}},
            {"id": "cap1", "type": "table_caption", "page": 1, "bbox": {"x": 100, "y": 60, "width": 400, "height": 30}, "text": "Table 1: Results"},
        ]
        PPStructureTableEngine._bind_table_captions(tables, elements)
        assert tables[0]["caption"] == "Table 1: Results"
        assert tables[0]["caption_id"] == "cap1"

    def test_table_caption_different_page_no_bind(self) -> None:
        from app.services.table_service import PPStructureTableEngine

        tables = [{"id": "t1", "page": 1, "bbox": {"x": 100, "y": 100, "width": 400, "height": 300}}]
        elements = [
            {"id": "cap1", "type": "table_caption", "page": 2, "bbox": {"x": 100, "y": 110, "width": 400, "height": 30}, "text": "Wrong page"},
        ]
        PPStructureTableEngine._bind_table_captions(tables, elements)
        assert not tables[0].get("caption")

    def test_table_no_bbox_skipped(self) -> None:
        from app.services.table_service import PPStructureTableEngine

        tables = [{"id": "t1", "page": 1}]  # no bbox
        elements = [
            {"id": "cap1", "type": "table_caption", "page": 1, "bbox": {"x": 100, "y": 110, "width": 400, "height": 30}, "text": "Cap"},
        ]
        PPStructureTableEngine._bind_table_captions(tables, elements)  # must not raise
        assert not tables[0].get("caption")
