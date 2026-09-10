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
    build_bank_statement,
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
    # Every amount cell (col 2) is confirmed against the text layer.
    # Date cells (col 0) may fall out as conservative mismatch because the
    # uniform grid over-approximates a non-uniform column width (R3 fallback).
    assert summary["cells_backfilled"] == 0, summary
    assert summary["cells_confirmed"] == 6, summary
    assert summary["cells_mismatch"] == 6, summary
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
