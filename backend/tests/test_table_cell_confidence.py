"""D8 aggregation rules: grouping, min, per-table frame choice and the hit-rate guard.

Pure logic, no Paddle/GPU. The geometries below mirror the three Cloud readings of
2026-10-09 (PENDING P-027 「产品侧立项 D8」): `invoices/multipage/invoice_multipage_3p_items.pdf`
(entry boxes matched the cells, one per non-empty cell), `test_data/testfiles/pdf/sample_report.pdf`
(up to 3 line-sized entries per cell) and `test_data/testfiles/GeneralFiles/bank_statement_sample.pdf`
(all entry boxes bottom-origin, i.e. `page_height - y` was needed - the entry boxes there are
used verbatim).
"""

from __future__ import annotations

import pytest

from app.services.table_cell_confidence import (
    DEFAULT_FRAME_OK_RATIO,
    aggregate_cell_confidence,
    as_box,
)


# --------------------------------------------------------------- geometry helpers

def test_as_box_accepts_four_numbers_and_polygon():
    assert as_box([1, 2, 30, 40]) == (1.0, 2.0, 30.0, 40.0)
    assert as_box([[0, 0], [10, 0], [10, 5], [0, 5]]) == (0.0, 0.0, 10.0, 5.0)
    assert as_box([3, 4]) is None


def test_as_box_refuses_non_geometry_without_recursing():
    assert as_box("abc") is None
    assert as_box(b"abc") is None
    assert as_box(None) is None
    assert as_box([[1, 2]]) is None


# --------------------------------------------------------------- aggregation

def _invoice_like():
    """Entry boxes match the cells; one cell is empty (None)."""
    cells = [
        [362.69, 946.95, 429.69, 965.95],
        [454.69, 947.95, 577.69, 965.95],
        [627.69, 948.95, 672.69, 966.95],  # empty <td>
    ]
    boxes = [[362.0, 947.0, 438.0, 961.0], [455.0, 947.0, 567.0, 961.0]]
    scores = [0.990791, 0.982971]
    return cells, boxes, scores


def test_single_entry_per_cell_raw_frame():
    cells, boxes, scores = _invoice_like()
    out = aggregate_cell_confidence(cells, boxes, scores, 1684)
    assert out["measured"] is True
    assert out["frame"] == "raw"
    assert out["cells"] == [0.990791, 0.982971, None]
    assert (out["hits"], out["unassigned"], out["n_rec"], out["n_cells"]) == (2, 0, 2, 3)


def test_line_level_entries_take_the_min():
    """sample_report pattern: one cell holding three line-sized entries."""
    cells = [[159.25, 180.4, 368.51, 243.35]]
    boxes = [[187, 187, 326, 208], [200, 215, 300, 230], [210, 232, 280, 241]]
    scores = [0.99, 0.91, 0.85]
    out = aggregate_cell_confidence(cells, boxes, scores, 1584)
    assert out["frame"] == "raw"
    assert out["cells"] == [0.85]
    assert out["hits"] == 3


def test_bank_statement_pattern_needs_the_flipped_frame():
    """The real entry boxes: raw misses every cell, `page_height - y` hits all of them."""
    h = 1584.0
    cells = [
        [99.0, 426.0, 278.0, 464.0],
        [278.0, 426.0, 779.0, 464.0],
        [779.0, 426.0, 958.7, 464.0],
        [958.7, 426.0, 1175.5, 464.0],
    ]
    boxes = [
        [163.0, 1124.0, 261.0, 1152.0],
        [372.0, 1123.0, 438.0, 1152.0],
        [771.0, 1124.0, 938.0, 1150.0],
    ]
    out = aggregate_cell_confidence(cells, boxes, [0.95, 0.99, 0.93], h)
    assert out["frame"] == "flip"
    assert out["measured"] is True
    assert out["cells"] == [0.95, 0.99, 0.93, None]
    assert out["hits"] == 3


def test_raw_frame_wins_when_it_hits_more_than_the_flip():
    """argmax, not "flip whenever it helps": here raw gets 2 and flip gets 0."""
    cells = [[0.0, 100.0, 200.0, 140.0], [0.0, 1500.0, 200.0, 1540.0]]
    boxes = [[10.0, 110.0, 40.0, 130.0], [10.0, 1510.0, 40.0, 1530.0]]
    out = aggregate_cell_confidence(cells, boxes, [0.9, 0.8], 1584)
    assert out["frame"] == "raw"
    assert out["hits"] == 2
    assert out["cells"] == [0.9, 0.8]


def test_entries_outside_every_cell_are_counted_not_attributed():
    """A boundary case for the guard: exactly 4/5 hits passes."""
    cells = [[0.0, 0.0, 100.0, 100.0]]
    boxes = [[10, 10, 40, 40], [20, 20, 50, 50], [30, 30, 60, 60], [40, 40, 70, 70], [500, 500, 520, 520]]
    out = aggregate_cell_confidence(cells, boxes, [0.9, 0.8, 0.7, 0.6, 0.4], 400)
    assert (out["hits"], out["unassigned"]) == (4, 1)
    assert out["measured"] is True
    assert out["cells"] == [0.6]


def test_hit_rate_guard_marks_the_whole_table_unmeasured():
    """Below DEFAULT_FRAME_OK_RATIO: unmeasured, every cell None, reason recorded."""
    assert DEFAULT_FRAME_OK_RATIO == 0.8
    cells = [[0.0, 0.0, 100.0, 100.0]]
    boxes = [[10, 10, 40, 40], [500, 500, 520, 520]]
    out = aggregate_cell_confidence(cells, boxes, [0.9, 0.4], 1000)
    assert out["measured"] is False
    assert out["frame"] is None
    assert out["reason"] == "frame_unresolved"
    assert out["cells"] == [None]


def test_degenerate_inputs_are_reported_not_raised():
    assert aggregate_cell_confidence([], [[1, 1, 2, 2]], [0.9], 100)["reason"] == "no_cells"
    assert aggregate_cell_confidence([[0, 0, 10, 10]], [], [], 100)["reason"] == "no_entries"
    assert aggregate_cell_confidence([], [], [], None)["cells"] == []


def test_missing_page_height_disables_only_the_flip_candidate():
    cells = [[0.0, 400.0, 100.0, 460.0]]
    boxes = [[10.0, 410.0, 40.0, 450.0]]
    assert aggregate_cell_confidence(cells, boxes, [0.9], None)["measured"] is True
    flipped = [[10.0, 1150.0, 40.0, 1190.0]]
    assert aggregate_cell_confidence(cells, flipped, [0.9], None)["reason"] == "frame_unresolved"


def test_scores_shorter_than_boxes_drop_the_tail():
    cells = [[0.0, 0.0, 100.0, 100.0], [200.0, 0.0, 300.0, 100.0]]
    out = aggregate_cell_confidence(cells, [[10, 10, 40, 40], [210, 10, 240, 40]], [0.7], 200)
    assert out["n_rec"] == 1
    assert out["cells"] == [0.7, None]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
