"""Tests for the E2 selective cell backfill funnel (all bbox/words mocked)."""

from __future__ import annotations

from app.services.table_alignment import (
    REASON_GEO,
    REASON_KEYS,
    REASON_NO_LINE,
    REASON_SANITY,
    REASON_VALUE_MATCH,
)
from app.services.table_backfill import (
    PROVENANCE_TEXT_BACKFILLED,
    PROVENANCE_TEXT_CONFIRMED,
    PROVENANCE_TEXT_MISMATCH,
    PROVENANCE_VISION,
    _finalize,
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
def _word(x0, y0, x1, y1, text, line=0, word=0):
    return [x0, y0, x1, y1, text, 0, line, word]


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
    assert table["cell_word_bbox"][0][0] == [10.0, 10.0, 40.0, 20.0]  # print anchor


def test_backfilled_when_ocr_confusion() -> None:
    # P-002: the amber branch requires the sanity gate (1 <-> l is a pinned
    # confusion pair, so the text layer wins and replaces the OCR value).
    table = _table([["l234"]])
    words = [_word(10, 10, 40, 20, "1234")]  # text layer correct
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["backfilled"] == 1
    assert table["data"][0][0] == "1234"  # replaced by text layer
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_BACKFILLED
    assert table["cell_ocr_text"][0][0] == "l234"  # original OCR kept
    assert table["cell_word_bbox"][0][0] == [10.0, 10.0, 40.0, 20.0]
    assert table["cell_align_reason"][0][0] == "geometric"


def test_sanity_reject_when_not_ocr_confusion() -> None:
    # P-002 flip #4 (design §3.6 flip list missed this one): "1234" vs "1284"
    # diverges with 3 <-> 8 not a pinned confusion pair, so the amber
    # replacement is refused and the cell goes red with data untouched.
    table = _table([["1234"]])
    words = [_word(10, 10, 40, 20, "1284")]
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["mismatch"] == 1
    assert stats["backfilled"] == 0
    assert table["data"][0][0] == "1234"  # NOT replaced
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_MISMATCH
    assert table["cell_align_reason"][0][0] == "sanity_reject"
    assert table["cell_ocr_text"][0][0] is None
    assert table["cell_word_bbox"][0][0] is None  # mismatch -> no anchor


def test_mismatch_when_text_layer_empty() -> None:
    table = _table([["1234"]])
    stats = backfill_table_cells(table, [], trusted=True)
    assert stats["mismatch"] == 1
    assert table["data"][0][0] == "1234"
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_MISMATCH
    assert table["cell_word_bbox"][0][0] is None  # no match -> no anchor


def test_confirmed_when_crossing_word_value_matched() -> None:
    # P-002 flip #1 (design §3.6): the word crosses the uniform cell edge but
    # T1 anchors it by row band + column window -> green, data untouched.
    table = _table([["1234"]])  # 1x1 grid -> cell bbox in pt: (0, 0, 100, 50)
    words = [_word(80, 10, 105, 20, "1234")]  # x1=105 > cell right edge 100
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["confirmed"] == 1
    assert stats["mismatch"] == 0
    assert table["data"][0][0] == "1234"
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_CONFIRMED
    assert table["cell_align_reason"][0][0] == "value_match"
    assert table["cell_word_bbox"][0][0] == [80.0, 10.0, 105.0, 20.0]  # T1 anchor


def test_confirmed_when_multi_line_joined_by_cluster() -> None:
    # P-002 flip #2 (design §3.6): two stacked lines join via T3 -> green
    # cluster; data untouched.
    table = _table([["1234"]])
    words = [
        _word(10, 10, 40, 15, "12", line=0),
        _word(10, 15, 40, 20, "34", line=1),
    ]
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["confirmed"] == 1
    assert stats["mismatch"] == 0
    assert table["data"][0][0] == "1234"  # unchanged
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_CONFIRMED
    assert table["cell_align_reason"][0][0] == "cluster"
    assert table["cell_word_bbox"][0][0] == [10.0, 10.0, 40.0, 20.0]


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
        _word(10, 10, 40, 20, "l234"),  # cell[0][0] backfilled (1<->l passes sanity)
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
    assert len(table["cell_word_bbox"]) == 2


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
            "reason": "no_aligned_line",
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


# --- P-002 C2: T1 integration (row band + column window anchoring) -------

def test_t1_row_band_hit_confirms_each_row() -> None:
    # 行带命中: each value resolves in its own row band (2x1 grid, rows
    # [0,25]/[25,50] pt).
    table = _table([["1234"], ["5678"]])
    words = [_word(10, 5, 40, 15, "1234"), _word(10, 30, 40, 40, "5678")]
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["confirmed"] == 2
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_CONFIRMED
    assert table["cell_provenance"][1][0] == PROVENANCE_TEXT_CONFIRMED
    assert table["cell_align_reason"][0][0] == REASON_VALUE_MATCH
    assert table["cell_align_reason"][1][0] == REASON_VALUE_MATCH


def test_t1_same_value_in_other_row_does_not_confirm() -> None:
    # Ying-3 regression anchor: a value printed in ANOTHER row never
    # resolves (i, j); the uncovered cell degrades honestly to T2/T3.
    table = _table([["1234"], ["1234"]])
    words = [_word(10, 30, 40, 40, "1234")]  # only inside row 1's band
    stats = backfill_table_cells(table, words, trusted=True)
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_MISMATCH
    assert table["cell_align_reason"][0][0] == REASON_NO_LINE  # not value_match
    assert table["cell_provenance"][1][0] == PROVENANCE_TEXT_CONFIRMED
    assert table["cell_align_reason"][1][0] == REASON_VALUE_MATCH


def test_t1_unique_value_in_other_column_does_not_confirm() -> None:
    # Ying-2A regression anchor: unique value, but printed in column 1's
    # x-range -> its word group anchors to column 1 and T1 refuses (0, 0).
    table = _table([["1234", ""]])
    words = [_word(90, 10, 100, 20, "1234")]  # center x=95 -> column 1 window
    stats = backfill_table_cells(table, words, trusted=True)
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_MISMATCH
    assert table["cell_align_reason"][0][0] == REASON_NO_LINE  # NOT value_match
    assert table["cell_provenance"][0][1] == PROVENANCE_VISION  # "" not candidate


def test_t1_multi_word_run_confirms() -> None:
    # 滑窗多词: consecutive words "12" + "345" join to the OCR value.
    table = _table([["12345"]])
    words = [_word(10, 10, 25, 20, "12", word=0), _word(27, 10, 45, 20, "345", word=1)]
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["confirmed"] == 1
    assert table["cell_align_reason"][0][0] == REASON_VALUE_MATCH
    assert table["cell_word_bbox"][0][0] == [10.0, 10.0, 45.0, 20.0]  # run union


def test_t1_collision_resolves_by_column_window() -> None:
    # 同行跨列同值 (G2c scenario ②): two "777" in row 0 -> COLLISION ->
    # the column window picks each cell's own word.
    table = _table([["777", "777"]])
    words = [_word(10, 10, 25, 20, "777", word=0), _word(60, 10, 75, 20, "777", word=1)]
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["confirmed"] == 2
    assert table["cell_align_reason"][0][0] == REASON_VALUE_MATCH
    assert table["cell_align_reason"][0][1] == REASON_VALUE_MATCH
    assert table["cell_word_bbox"][0][0] == [10.0, 10.0, 25.0, 20.0]
    assert table["cell_word_bbox"][0][1] == [60.0, 10.0, 75.0, 20.0]


def test_t1_collision_tie_falls_back_to_t2() -> None:
    # 并列最近 -> ambiguous -> T1 refuses; T2 joins both words on one line
    # and "777777" diverges beyond the confusion set -> honest red.
    table = _table([["777", "777"]])
    words = [_word(10, 10, 20, 20, "777", word=0), _word(30, 10, 40, 20, "777", word=1)]
    stats = backfill_table_cells(table, words, trusted=True)
    assert stats["confirmed"] == 0
    assert stats["mismatch"] == 2
    assert table["cell_align_reason"][0][0] == REASON_SANITY
    assert table["cell_align_reason"][0][1] == REASON_NO_LINE
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_MISMATCH


def test_t1_sibling_table_words_excluded() -> None:
    # 兄弟表排除 (D9/R3): a word centered inside a sibling's rect never
    # enters the neighborhood -> T1 blocked; T2 (sibling-agnostic) confirms.
    table = _table([["1234"]])
    words = [_word(10, 10, 40, 20, "1234")]
    stats = backfill_table_cells(
        table, words, trusted=True, sibling_bboxes=[(5.0, 5.0, 45.0, 25.0)]
    )
    assert stats["confirmed"] == 1
    assert table["cell_align_reason"][0][0] == REASON_GEO  # T1 was blocked
    assert table["cell_provenance"][0][0] == PROVENANCE_TEXT_CONFIRMED


# --- P-002 C2: _finalize single write point (§3.3.1-e) --------------------


def _finalize_env(cell_text):
    row = [cell_text]
    return (
        row,
        [PROVENANCE_VISION],
        [None],
        [None],
        [None],
        {"candidates": 1, "confirmed": 0, "backfilled": 0, "mismatch": 0},
        {key: 0 for key in REASON_KEYS},
    )


def _call_finalize(provenance, reason, words, text_layer_text, cell_text):
    row, prov_row, ocr_row, wb_row, reason_row, stats, counts = _finalize_env(cell_text)
    _finalize(
        provenance=provenance, reason=reason, words=words,
        text_layer_text=text_layer_text, cell_text=cell_text,
        i=0, j=0, row=row, prov_row=prov_row, ocr_row=ocr_row,
        wb_row=wb_row, reason_row=reason_row, stats=stats,
        reason_counts=counts,
    )
    return row, prov_row, ocr_row, wb_row, reason_row, stats, counts


def test_finalize_backfilled_writes_data_and_ocr_original() -> None:
    word = _word(10, 10, 40, 20, "1234")
    row, prov_row, ocr_row, wb_row, reason_row, stats, counts = _call_finalize(
        PROVENANCE_TEXT_BACKFILLED, REASON_GEO, [word], "1234", "l234"
    )
    assert row[0] == "1234"  # data replaced by the text layer value
    assert ocr_row[0] == "l234"  # OCR original preserved
    assert wb_row[0] == [10.0, 10.0, 40.0, 20.0]
    assert reason_row[0] == REASON_GEO
    assert stats["backfilled"] == 1
    assert counts["geometric"] == 1


def test_finalize_confirmed_leaves_data_untouched() -> None:
    word = _word(10, 10, 40, 20, "1234")
    row, prov_row, ocr_row, wb_row, reason_row, stats, counts = _call_finalize(
        PROVENANCE_TEXT_CONFIRMED, REASON_VALUE_MATCH, [word], "1234", "1234"
    )
    assert row[0] == "1234"  # unchanged
    assert ocr_row[0] is None
    assert wb_row[0] == [10.0, 10.0, 40.0, 20.0]
    assert reason_row[0] == REASON_VALUE_MATCH
    assert stats["confirmed"] == 1
    assert counts["value_match"] == 1


def test_finalize_mismatch_writes_no_anchor_and_no_data() -> None:
    word = _word(10, 10, 40, 20, "1284")
    row, prov_row, ocr_row, wb_row, reason_row, stats, counts = _call_finalize(
        PROVENANCE_TEXT_MISMATCH, REASON_SANITY, [word], "1284", "1234"
    )
    assert row[0] == "1234"  # data untouched
    assert ocr_row[0] is None
    assert wb_row[0] is None  # mismatch -> no anchor
    assert reason_row[0] == REASON_SANITY
    assert stats["mismatch"] == 1
    assert counts["sanity_reject"] == 1


def test_finalize_reason_counts_stay_eight_key_closed() -> None:
    word = _word(10, 10, 40, 20, "1234")
    _, _, _, _, _, stats1, counts1 = _call_finalize(
        PROVENANCE_TEXT_CONFIRMED, REASON_VALUE_MATCH, [word], "1234", "1234"
    )
    _, _, _, _, _, stats2, counts2 = _call_finalize(
        PROVENANCE_TEXT_BACKFILLED, REASON_GEO, [word], "1234", "l234"
    )
    assert set(counts1) == set(REASON_KEYS) and len(REASON_KEYS) == 8
    assert sum(counts1.values()) == stats1["confirmed"] + stats1["backfilled"] + stats1["mismatch"]
    assert sum(counts2.values()) == 1
    assert counts2["geometric"] == 1
