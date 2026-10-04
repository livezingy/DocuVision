"""Golden backfill integration tests (v1.8 §8.2, CPU-safe subset).

Uses the deterministic trial sample generators to verify the backfill funnel
against a real PDF text layer. The visual table dict is reconstructed from
the known generator geometry, so no GPU / PP-StructureV3 is required locally.
"""

from __future__ import annotations

import os
import sys

import fitz
import pytest

_SCRIPTS_TRIAL = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "trial")
)
if _SCRIPTS_TRIAL not in sys.path:
    sys.path.insert(0, _SCRIPTS_TRIAL)

from generate_trial_samples import (  # noqa: E402
    SYMBOL_NAMES,
    SYMBOLS,
    build_bank_statement,
    build_merged_band_table,
    build_nonuniform_table,
    build_symbol_grid,
    find_font,
)

from app.services.page_text_trust import judge_page_trust  # noqa: E402
from app.services.table_backfill import backfill_tables  # noqa: E402


def _font() -> str:
    try:
        return find_font()
    except SystemExit:
        pytest.skip("no symbol-capable font found")


def _write(doc, path) -> None:
    doc.save(path)
    doc.close()


def test_bank_statement_generator_is_trusted(tmp_path) -> None:
    path = str(tmp_path / "bank_statement.pdf")
    _write(build_bank_statement(_font()), path)
    doc = fitz.open(path)
    try:
        result = judge_page_trust(doc[0])
        assert result.trusted, result.signals
        assert result.verdict == "text_layer"
    finally:
        doc.close()


def test_symbol_grid_generator_is_trusted(tmp_path) -> None:
    path = str(tmp_path / "symbol_grid.pdf")
    _write(build_symbol_grid(_font()), path)
    doc = fitz.open(path)
    try:
        result = judge_page_trust(doc[0])
        assert result.trusted, result.signals
    finally:
        doc.close()


def test_bank_statement_backfill_confirms_amounts(tmp_path) -> None:
    path = str(tmp_path / "bank_statement.pdf")
    _write(build_bank_statement(_font()), path)

    # Reconstruct the visual table dict from generator geometry.
    # _grid_table: top=80, left=40 (PDF pt), col_widths=[120,210,170], row_h=24.
    # Raster space (Matrix 2x2) = PDF pt * 2.
    rows = [
        ["Date", "Description", "Amount (USD)"],
        ["2024-01-05", "Opening balance", "1,250.00"],
        ["2024-01-12", "Invoice payment", "3,480.25"],
        ["2024-01-20", "Wire transfer", "12,900.00"],
        ["2024-02-01", "Service fee", "45.50"],
        ["2024-02-10", "Refund", "-250.00"],
        ["2024-02-18", "Closing balance", "17,425.75"],
    ]
    table = {
        "id": "t1",
        "page": 1,
        "bbox": {
            "x": 40 * 2,
            "y": 80 * 2,
            "width": (120 + 210 + 170) * 2,
            "height": (len(rows) * 24) * 2,
        },
        "data": rows,
    }

    summary = backfill_tables([table], path, enabled=True)
    assert summary["pages_text_layer_trusted"] == 1
    # 6 date cells + 6 amount cells are candidates; header/description are not.
    assert summary["cells_candidates"] == 12, summary
    # P-002 G2a: T1 row-band + column-window value matching resolves the
    # dates too — the uniform-grid mismatch (non-uniform columns) is gone.
    assert summary["cells_backfilled"] == 0, summary
    assert summary["cells_confirmed"] == 12, summary
    assert summary["cells_mismatch"] == 0, summary
    assert summary["cells_candidates"] == (
        summary["cells_confirmed"]
        + summary["cells_backfilled"]
        + summary["cells_mismatch"]
    )
    # Amount cell in row 1, col 2 is text_confirmed.
    assert table["cell_provenance"][1][2] == "text_confirmed"
    assert table["cell_ocr_text"][1][2] is None
    # Amount text untouched (vision already correct).
    assert table["data"][1][2] == "1,250.00"
    # The previously-red date cells now confirm via T1 (value_match).
    assert table["cell_provenance"][1][0] == "text_confirmed"
    assert table["cell_align_reason"][1][0] == "value_match"
    # G2a full pin: 12 x value_match, all other reasons zero.
    assert summary["align_reason_counts"] == {
        "value_match": 12,
        "geometric": 0,
        "cluster": 0,
        "sanity_reject": 0,
        "no_aligned_line": 0,
        "crossing": 0,
        "multi_line": 0,
        "shape_mismatch": 0,
        "band_range_incomplete": 0,
    }


def test_symbol_grid_backfill_symbols_value_match(tmp_path) -> None:
    # P-002 G2b (ruling X2, 2026-09-29): the symbol glyphs survive in the
    # text layer, are row-unique and column-anchored -> T1 flips the former
    # 4 reds (uniform-grid overhang pulled neighbour words into the cells)
    # to green value_match.
    path = str(tmp_path / "symbol_grid.pdf")
    _write(build_symbol_grid(_font()), path)
    rows = [
        ["Symbol", "Name", "Unicode", "Risk"],
        [SYMBOLS[0], SYMBOL_NAMES[SYMBOLS[0]], "U+2713", "low risk"],
        [SYMBOLS[1], SYMBOL_NAMES[SYMBOLS[1]], "U+2297", "at risk"],
        [SYMBOLS[2], SYMBOL_NAMES[SYMBOLS[2]], "U+25CF", "low risk"],
        [SYMBOLS[3], SYMBOL_NAMES[SYMBOLS[3]], "U+25CB", "at risk"],
    ]
    table = {
        "id": "t1",
        "page": 1,
        "bbox": {
            "x": 40 * 2,
            "y": 80 * 2,
            "width": (80 + 180 + 100 + 140) * 2,
            "height": (len(rows) * 28) * 2,
        },
        "data": rows,
    }
    summary = backfill_tables([table], path, enabled=True)
    assert summary["pages_text_layer_trusted"] == 1
    assert summary["cells_candidates"] == 4, summary
    assert summary["cells_confirmed"] == 4, summary
    assert summary["cells_backfilled"] == 0, summary
    assert summary["cells_mismatch"] == 0, summary
    assert summary["align_reason_counts"] == {
        "value_match": 4,
        "geometric": 0,
        "cluster": 0,
        "sanity_reject": 0,
        "no_aligned_line": 0,
        "crossing": 0,
        "multi_line": 0,
        "shape_mismatch": 0,
        "band_range_incomplete": 0,
    }
    assert table["cell_align_reason"][1][0] == "value_match"
    assert table["cell_provenance"][4][0] == "text_confirmed"


def test_nonuniform_table_golden(tmp_path) -> None:
    # P-002 G2c: per-cell pins on the non-uniform golden — T1 collision
    # resolved by the column window, crossing word rescued by T1, stacked
    # lines joined by T3, the Ying-2A other-column refusal, and one
    # intentionally unsolvable cell (honest red).
    path = str(tmp_path / "nonuniform_table.pdf")
    _write(build_nonuniform_table(_font()), path)
    rows = [
        ["Ref", "Note", "Amt"],
        ["777", "777", ""],
        ["12345", "", "55.25"],
        ["1234", "8888", "7777"],
    ]
    table = {
        "id": "t1",
        "page": 1,
        "bbox": {
            "x": 40 * 2,
            "y": 80 * 2,
            "width": (140 + 110 + 100) * 2,
            "height": (len(rows) * 24) * 2,
        },
        "data": rows,
    }
    summary = backfill_tables([table], path, enabled=True)
    assert summary["pages_text_layer_trusted"] == 1
    assert summary["cells_candidates"] == 7, summary
    assert summary["cells_confirmed"] == 5, summary
    assert summary["cells_backfilled"] == 0, summary
    assert summary["cells_mismatch"] == 2, summary
    reasons = table["cell_align_reason"]
    assert reasons[1][0] == "value_match"  # collision -> column window
    assert reasons[1][1] == "value_match"
    assert reasons[2][0] == "cluster"  # stacked "12"/"345" joined by T3
    assert reasons[2][2] == "value_match"
    assert reasons[3][0] == "value_match"  # crossing word rescued by T1
    assert reasons[3][1] == "no_aligned_line"  # Ying-2A: NOT value_match
    assert reasons[3][2] == "no_aligned_line"  # unsolvable: honest red
    assert table["data"][2][0] == "12345"  # cluster green leaves data untouched
    counts = summary["align_reason_counts"]
    assert counts["value_match"] == 4
    assert counts["cluster"] == 1
    assert counts["no_aligned_line"] == 2
    assert sum(counts.values()) == summary["cells_candidates"]


def test_merged_band_cell_flagged_band_range_incomplete(tmp_path) -> None:
    # P-028 G1: the merged band cell whose OCR text lost the end decimal
    # point (X1=B verdict — recognition-layer loss, assembly lossless) is
    # flagged band_range_incomplete with the original string passed through
    # verbatim (no silent fix); the legal control row walks the funnel
    # unchanged (value_match) and carries no band_range key.
    path = str(tmp_path / "merged_band_table.pdf")
    _write(build_merged_band_table(_font()), path)
    rows = [
        ["Frequency Band (MHz)", "Note"],
        ["40.7-4098MHz", ""],  # merged cell text (spans vision rows 1-2)
        ["", ""],
        ["40.66 - 40.7 MHz", "control"],
    ]
    table = {
        "id": "t1",
        "page": 1,
        "bbox": {
            "x": 40 * 2,
            "y": 80 * 2,
            "width": (200 + 160) * 2,
            "height": (len(rows) * 24) * 2,
        },
        "data": rows,
    }
    summary = backfill_tables([table], path, enabled=True)
    assert summary["pages_text_layer_trusted"] == 1
    assert summary["cells_candidates"] == 2, summary  # band cell + control cell
    assert summary["cells_mismatch"] == 1, summary
    assert summary["cells_confirmed"] == 1, summary
    # the merged cell: flagged, original string passes through verbatim
    assert table["cell_provenance"][1][0] == "text_mismatch"
    assert table["cell_align_reason"][1][0] == "band_range_incomplete"
    assert table["data"][1][0] == "40.7-4098MHz"
    # diagnosis carries raw + flags + both endpoint texts
    details = summary["mismatch_details"]
    assert len(details) == 1, details
    diag = details[0]
    assert diag["row"] == 1 and diag["col"] == 0
    assert diag["reason"] == "band_range_incomplete"
    assert diag["band_range"] == {
        "raw": "40.7-4098MHz",
        "flags": ["magnitude_gap"],
        "start_text": "40.7",
        "end_text": "4098",
    }
    # the control row walks the funnel unchanged (confirmed, not in details)
    assert table["cell_provenance"][3][0] == "text_confirmed"
    assert table["cell_align_reason"][3][0] == "value_match"
    counts = summary["align_reason_counts"]
    assert counts["band_range_incomplete"] == 1
    assert counts["value_match"] == 1
