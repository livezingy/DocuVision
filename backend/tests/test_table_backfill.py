"""Tests for the E2 selective cell backfill funnel (all bbox/words mocked)."""

from __future__ import annotations

from app.services.table_backfill import (
    PROVENANCE_TEXT_BACKFILLED,
    PROVENANCE_TEXT_CONFIRMED,
    PROVENANCE_TEXT_MISMATCH,
    PROVENANCE_VISION,
    backfill_table_cells,
    backfill_tables,
    is_candidate_cell,
)


def _table(data, bbox=None):
    return {
        "id": "t1",
        "page": 1,
        "engine": "PP-Structure-Table",
        "bbox": bbox or {"x": 0, "y": 0, "width": 200, "height": 100},
        "data": data,
    }


# word tuple: (x0, y0, x1, y1, text, block_no, line_no, word_no)
def _word(x0, y0, x1, y1, text, line=0):
    return [x0, y0, x1, y1, text, 0, line, 0]


def test_is_candidate_cell() -> None:
    assert is_candidate_cell("1,234.56")  # amount
    assert is_candidate_cell("123")  # number
    assert is_candidate_cell("2024-01-15")  # date
    assert is_candidate_cell("IBAN12345")  # code
    assert is_candidate_cell("✓")  # symbol
    assert not is_candidate_cell("")  # empty
    assert not is_candidate_cell("Name")  # short non-numeric
    assert not is_candidate_cell(
        "This is a long prose cell that should never be backfilled"
    )


def test_confirmed_when_text_matches() -> None:
    table = _table([["1234"]])
    words = [_word(10, 10, 40, 20, "1234")]
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["candidates"] == 1
    assert stats["confirmed"] == 1
    assert stats["backfilled"] == 0
    assert table["data"][0][0] == "1234"  # unchanged
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_CONFIRMED
    assert table["cell_ocr_text"][0][0] is None


def test_backfilled_when_numeric_diverges() -> None:
    table = _table([["1234"]])
    words = [_word(10, 10, 40, 20, "1284")]  # text layer correct
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["backfilled"] == 1
    assert table["data"][0][0] == "1284"  # replaced by text layer
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_BACKFILLED
    assert table["cell_ocr_text"][0][0] == "1234"  # original OCR kept


def test_mismatch_when_text_layer_empty() -> None:
    table = _table([["1234"]])
    stats = backfill_table_cells(table, [], trusted=True)
    assert stats["mismatch"] == 1
    assert table["data"][0][0] == "1234"
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_MISMATCH


def test_mismatch_when_word_crosses_cell_boundary() -> None:
    table = _table([["1234"]])  # 1x1 grid -> cell bbox in pt: (0, 0, 100, 50)
    words = [_word(80, 10, 105, 20, "1234")]  # x1=105 > cell right edge 100
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["mismatch"] == 1
    assert table["data"][0][0] == "1234"
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_MISMATCH


def test_mismatch_when_multiple_text_lines() -> None:
    table = _table([["1234"]])
    words = [
        _word(10, 10, 40, 15, "12", line=0),
        _word(10, 15, 40, 20, "34", line=1),
    ]
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["mismatch"] == 1
    assert table["data"][0][0] == "1234"


def test_untrusted_page_zero_backfill() -> None:
    table = _table([["1234"]])
    words = [_word(10, 10, 40, 20, "1234")]
    stats = backfill_table_cells(table, words, trusted=False)
    assert stats["candidates"] == 0
    assert stats["confirmed"] == 0
    assert table["cell_provenance"][0][0] == PROVENANCE_VISION
    assert "cell_ocr_text" in table


def test_counts_are_self_consistent() -> None:
    # 2x2 grid in pt: cells (0,0,50,25) (50,0,100,25) (0,25,50,50) (50,25,100,50)
    table = _table([["1234", "Name"], ["2024-01-15", "✓"]])
    words = [
        _word(10, 10, 40, 20, "1284"),  # cell[0][0] backfilled
        _word(10, 30, 40, 45, "2024-01-15"),  # cell[1][0] confirmed
        _word(60, 30, 70, 45, "✓"),  # cell[1][1] confirmed (symbol)
    ]
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["candidates"] == 3  # "Name" is not a candidate
    assert stats["confirmed"] == 2
    assert stats["backfilled"] == 1
    assert stats["mismatch"] == 0
    assert stats["candidates"] == stats["confirmed"] + stats["backfilled"] + stats["mismatch"]
    # provenance grid aligns with data shape
    assert len(table["cell_provenance"]) == 2
    assert len(table["cell_provenance"][0]) == 2


def _one_page_pdf(tmp_path):
    # One page with a (trusted) text layer; the single word sits well outside
    # the table rect so every candidate cell finds no aligned text line.
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 700), "hello")
    path = tmp_path / "one_page.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_mismatch_records_capture_details() -> None:
    table = _table([["1234"]])
    records: list = []
    stats = backfill_table_cells(
        table, [], trusted=True, mismatch_records=records, table_index=2, page_num=3
    )
    assert stats["mismatch"] == 1
    assert records == [
        {
            "page": 3,
            "table_index": 2,
            "row": 0,
            "col": 0,
            "ocr_text": "1234",
            "text_layer_text": "",
        }
    ]
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_MISMATCH


def test_backfill_tables_collects_and_caps_mismatch_details(tmp_path) -> None:
    path = _one_page_pdf(tmp_path)
    rows = 10
    cols = 6
    data = [[str(100 + r * cols + c) for c in range(cols)] for r in range(rows)]
    table = _table(data, bbox={"x": 200, "y": 200, "width": 600, "height": 400})

    summary = backfill_tables([table], path, enabled=True)

    assert summary["pages_skipped_preprocessed"] == 0  # default params: old behavior
    assert summary["cells_candidates"] == rows * cols
    assert summary["cells_mismatch"] == rows * cols
    assert len(summary["mismatch_details"]) == 50
    assert summary["mismatch_details_truncated"] == rows * cols - 50
    first = summary["mismatch_details"][0]
    assert first["page"] == 1 and first["table_index"] == 0
    assert first["ocr_text"] == data[0][0]
    assert first["text_layer_text"] == ""


def test_backfill_tables_gate_skips_deskewed_pages(tmp_path) -> None:
    path = _one_page_pdf(tmp_path)
    table = _table([["1234"]], bbox={"x": 200, "y": 200, "width": 600, "height": 400})

    summary = backfill_tables([table], path, enabled=True, angle_deg=12.0)
    assert summary["pages_skipped_preprocessed"] == 1
    assert summary["pages_judged"] == 0
    assert summary["cells_candidates"] == 0
    assert summary["mismatch_details"] == []
    assert summary["page_verdicts"] == []


def test_backfill_tables_gate_skips_unwarped_pages(tmp_path) -> None:
    path = _one_page_pdf(tmp_path)
    table = _table([["1234"]], bbox={"x": 200, "y": 200, "width": 600, "height": 400})

    summary = backfill_tables([table], path, enabled=True, use_doc_unwarping=True)
    assert summary["pages_skipped_preprocessed"] == 1
    assert summary["cells_candidates"] == 0
