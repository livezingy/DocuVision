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
    LOW_CONFIDENCE_CUT,
    _project_cell_confidence,
    aggregate_cell_confidence,
    as_box,
    attach_cell_confidence,
    cell_confidence_from_table_item,
    page_height_of,
    summarize_cell_confidence,
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


# --------------------------------------------------------------- engine adapters

def test_page_height_reads_the_payload_height():
    assert page_height_of({"height": 1584}) == 1584.0
    assert page_height_of({"height": None}) == 0.0
    assert page_height_of({"height": "oops"}) == 0.0
    assert page_height_of({}) == 0.0
    assert page_height_of(None) == 0.0


def test_page_height_never_falls_back_to_a_synthetic_box():
    """A payload with only an image must NOT borrow _infer_page_bbox's 1400 fallback."""
    class _Item:
        img = [[0, 0], [0, 0]]

    assert page_height_of(_Item()) == 0.0


def test_cell_confidence_from_table_item_shape():
    item = {
        "cell_box_list": [[0.0, 0.0, 100.0, 100.0], [200.0, 0.0, 300.0, 100.0]],
        "table_ocr_pred": {"rec_boxes": [[10, 10, 40, 40]], "rec_scores": [0.8]},
    }
    payload = cell_confidence_from_table_item(item, 500)
    assert payload == {
        "cells": [0.8, None],
        "frame": "raw",
        "measured": True,
        "reason": "ok",
        "hits": 1,
        "n_rec": 1,
        "n_cells": 2,
    }


def test_cell_confidence_is_none_without_the_ocr_payload():
    assert cell_confidence_from_table_item({"cell_box_list": [[0, 0, 1, 1]]}, 100) is None
    assert cell_confidence_from_table_item({}, 100) is None


def test_cell_confidence_from_table_item_reads_numpy_fields():
    """2026-10-14 worker crash: ``rec_boxes``/``rec_scores`` arrive as ``np.ndarray``.

    Asking a raw ``(N, 4)`` array for its truth value (``field or []``) raises
    ``ValueError: The truth value of an array with more than one element is ambiguous``
    from inside ``_parse_result`` — which runs **in the worker subprocess** for the
    page-by-page PDF driver, so one table killed the whole page (four fixtures,
    ``layout_elements_n=0``). The aggregation itself has always been array-safe; only the
    fallbacks were not.
    """
    np = pytest.importorskip("numpy")
    item = {
        "cell_box_list": np.array([[0.0, 0.0, 100.0, 100.0], [200.0, 0.0, 300.0, 100.0]]),
        "table_ocr_pred": {
            "rec_boxes": np.array([[10.0, 10.0, 40.0, 40.0], [210.0, 10.0, 240.0, 40.0]]),
            "rec_polys": "never reached: rec_boxes wins",
            "rec_scores": np.array([0.8, 0.7]),
        },
    }
    payload = cell_confidence_from_table_item(item, 500)
    assert payload["measured"] is True
    assert payload["frame"] == "raw"
    assert payload["cells"] == [0.8, 0.7]
    assert (payload["hits"], payload["n_rec"], payload["n_cells"]) == (2, 2, 2)


def test_cell_confidence_falls_back_to_rec_polys_and_tolerates_scalars():
    """The rec_polys fallback must survive being an array too; junk stays unmeasured."""
    np = pytest.importorskip("numpy")
    item = {
        "cell_box_list": np.array([[0.0, 0.0, 100.0, 100.0]]),
        "table_ocr_pred": {
            "rec_polys": np.array([[10.0, 10.0, 40.0, 10.0, 40.0, 40.0, 10.0, 40.0]]),
            "rec_scores": np.array([0.6]),
        },
    }
    payload = cell_confidence_from_table_item(item, 500)
    assert payload["cells"] == [0.6]

    # Non-iterable fields degrade to "no entries" rather than raising mid-page.
    broken = {"table_ocr_pred": {"rec_boxes": 3.5, "rec_scores": None}}
    assert cell_confidence_from_table_item(broken, 500) is None


def test_page_height_of_a_numpy_field_is_not_a_truth_value_error():
    np = pytest.importorskip("numpy")
    assert page_height_of({"height": np.float64(1584.0)}) == 1584.0
    # An array height cannot be a page height: the flip candidate is dropped, not raised.
    assert page_height_of({"height": np.array([1584.0, 1000.0])}) == 0.0


def test_attach_cell_confidence_matches_by_id_and_leaves_others_alone():
    elements = [
        {"id": "p1_table_1", "cell_confidence": {"cells": [0.9], "measured": True}},
        {"id": "p1_e0", "type": "text"},
    ]
    tables = [{"id": "p1_table_1"}, {"id": "p9_table_9"}]
    assert attach_cell_confidence(tables, elements) == 1
    assert tables[0]["cell_confidence"]["cells"] == [0.9]
    assert "cell_confidence" not in tables[1]


# ------------------------------------------------- P-027 A: merged-cell projection

def _merged_table():
    """3x3 grid from 7 <td>: colspan placeholder + rowspan continuation.

    Same fixture as the span_map characterization in test_table_header_structure.py:
    ``data == [['A', '', 'B'], ['C', 'D', ''], ['E', 'F', 'G']]``.
    """
    return {
        "id": "p1_table_1",
        "data": [["A", "", "B"], ["C", "D", ""], ["E", "F", "G"]],
        "html_structure": {"span_map": [
            {"row": 0, "col": 0, "rowspan": 1, "colspan": 2},
            {"row": 0, "col": 2, "rowspan": 2, "colspan": 1},
            {"row": 1, "col": 0, "rowspan": 1, "colspan": 1},
            {"row": 1, "col": 1, "rowspan": 1, "colspan": 1},
            {"row": 2, "col": 0, "rowspan": 1, "colspan": 1},
            {"row": 2, "col": 1, "rowspan": 1, "colspan": 1},
            {"row": 2, "col": 2, "rowspan": 1, "colspan": 1},
        ]},
        "cell_confidence": {
            "cells": [0.91, 0.95, 0.88, 0.97, 0.93, 0.99, 0.89],
            "frame": "raw", "measured": True, "reason": "ok",
            "hits": 7, "n_rec": 7, "n_cells": 7,
        },
    }


def test_projection_writes_scores_at_anchors_and_none_at_continuations():
    table = _merged_table()
    assert _project_cell_confidence(table) is True
    # 9 grid positions from 7 values: anchors carry the score, continuations None.
    assert table["cell_confidence_grid"] == [
        [0.91, None, 0.95],
        [0.88, 0.97, None],
        [0.93, 0.99, 0.89],
    ]
    assert table["cell_td_span"] == _merged_table()["html_structure"]["span_map"]


def test_projection_without_merge_is_row_major_equivalent():
    table = {
        "id": "t",
        "data": [["1", "2"], ["3", "4"]],
        "html_structure": {"span_map": [
            {"row": 0, "col": 0, "rowspan": 1, "colspan": 1},
            {"row": 0, "col": 1, "rowspan": 1, "colspan": 1},
            {"row": 1, "col": 0, "rowspan": 1, "colspan": 1},
            {"row": 1, "col": 1, "rowspan": 1, "colspan": 1},
        ]},
        "cell_confidence": {"cells": [0.9, 0.8, 0.7, 0.6], "measured": True},
    }
    assert _project_cell_confidence(table) is True
    assert table["cell_confidence_grid"] == [[0.9, 0.8], [0.7, 0.6]]


def test_projection_degrades_without_span_map_and_attaches_nothing():
    table = {"id": "t", "data": [["A"]], "cell_confidence": {"cells": [0.9], "measured": True}}
    assert _project_cell_confidence(table) is False
    assert "cell_confidence_grid" not in table
    assert "cell_td_span" not in table


def test_projection_degrades_on_length_mismatch():
    table = _merged_table()
    table["html_structure"]["span_map"] = table["html_structure"]["span_map"][:6]
    assert _project_cell_confidence(table) is False
    assert "cell_confidence_grid" not in table


def test_projection_degrades_on_out_of_bounds_anchor():
    table = _merged_table()
    table["html_structure"]["span_map"][3]["row"] = 9
    assert _project_cell_confidence(table) is False
    assert "cell_confidence_grid" not in table


def test_projection_degrades_when_a_covered_cell_is_not_blank():
    """Guard 5: text inside a 'continuation' means the walks drifted -- degrade."""
    table = _merged_table()
    table["data"][0][1] = "drifted text"  # colspan continuation of the A anchor
    assert _project_cell_confidence(table) is False
    assert "cell_confidence_grid" not in table


def test_projection_is_decoupled_from_the_backfill_trust_gate():
    """A measured=False payload still gets its grid: no page-trust input exists here."""
    table = _merged_table()
    table["cell_confidence"] = {
        "cells": [None] * 7, "frame": None, "measured": False,
        "reason": "frame_unresolved", "hits": 0, "n_rec": 7, "n_cells": 7,
    }
    assert _project_cell_confidence(table) is True
    assert table["cell_confidence_grid"] == [[None] * 3 for _ in range(3)]


def test_attach_cell_confidence_projects_the_grid_too():
    element = {"id": "p1_table_1", "cell_confidence": _merged_table()["cell_confidence"]}
    table = _merged_table()
    table.pop("cell_confidence")
    assert attach_cell_confidence([table], [element]) == 1
    assert table["cell_confidence_grid"][0][0] == 0.91
    assert len(table["cell_td_span"]) == 7


def test_summarize_counts_measured_unmeasured_and_low():
    assert LOW_CONFIDENCE_CUT == 0.90
    summary = summarize_cell_confidence(_merged_table())
    assert summary == {
        "measured": True, "n_cells": 7,
        "cells_measured": 7, "cells_unmeasured": 0, "cells_low": 2,  # 0.88, 0.89
    }


def test_summarize_mixed_cells_counts_none_as_unmeasured():
    table = {"cell_confidence": {"cells": [0.95, None, 0.85], "measured": True}}
    summary = summarize_cell_confidence(table)
    assert (summary["cells_measured"], summary["cells_unmeasured"], summary["cells_low"]) == (2, 1, 1)


def test_summarize_low_cut_is_exclusive_at_the_boundary():
    table = {"cell_confidence": {"cells": [0.90, 0.899], "measured": True}}
    assert summarize_cell_confidence(table)["cells_low"] == 1  # 0.90 itself is not low


def test_summarize_unmeasured_table_reports_every_cell_unmeasured():
    table = {"cell_confidence": {"cells": [None, None, None], "measured": False}}
    assert summarize_cell_confidence(table) == {
        "measured": False, "n_cells": 3, "cells_measured": 0,
        "cells_unmeasured": 3, "cells_low": 0,
    }


def test_summarize_missing_payload_is_all_zero():
    assert summarize_cell_confidence({}) == {
        "measured": False, "n_cells": 0, "cells_measured": 0,
        "cells_unmeasured": 0, "cells_low": 0,
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
