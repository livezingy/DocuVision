"""Unit tests for table_alignment (P-002): sanity gate, reason contract, T1/T3.

Pure logic — no paddle, no server (testing.md local layer).
"""

from __future__ import annotations

from app.services.table_alignment import (
    PROVENANCE_BACKFILLED_LITERAL,
    PROVENANCE_CONFIRMED_LITERAL,
    PROVENANCE_MISMATCH_LITERAL,
    REASON_BAND_RANGE,
    REASON_CLUSTER,
    REASON_CROSSING,
    REASON_GEO,
    REASON_KEYS,
    REASON_MULTI,
    REASON_NO_LINE,
    REASON_SANITY,
    REASON_SHAPE,
    REASON_VALUE_MATCH,
    T1Status,
    build_layout_model,
    collect_t3_words,
    is_ocr_confusion,
    resolve_t1_collision,
    solve_t1,
    solve_t3,
)
from app.services.table_backfill import (
    PROVENANCE_TEXT_BACKFILLED,
    PROVENANCE_TEXT_CONFIRMED,
    PROVENANCE_TEXT_MISMATCH,
)


def test_reason_enum_is_closed() -> None:
    assert REASON_KEYS == (
        REASON_VALUE_MATCH,
        REASON_GEO,
        REASON_CLUSTER,
        REASON_SANITY,
        REASON_NO_LINE,
        REASON_CROSSING,
        REASON_MULTI,
        REASON_SHAPE,
        REASON_BAND_RANGE,
    )
    assert len(set(REASON_KEYS)) == 9


def test_equal_length_single_confusion_passes() -> None:
    assert is_ocr_confusion("l1", "11")  # 1 <-> l; 1 replacement, len 2 -> cap 1
    assert is_ocr_confusion("O", "0")  # 0 <-> O
    assert is_ocr_confusion("√", "✓")  # pinned pair
    assert is_ocr_confusion("1234", "1234")  # identical


def test_equal_length_two_confusions_len7_passes() -> None:
    # len 7 -> cap 2; "1l0,00O" vs "110,000": 1<->l and O<->0.
    assert is_ocr_confusion("1l0,00O", "110,000")


def test_non_confusable_pair_rejects() -> None:
    # Rule 2 dominates: "2" <-> "9" is not a pinned pair (1 mismatch only).
    assert not is_ocr_confusion("250", "950")
    # The design draft §3.2 illustrated "125,000" <-> "129,00O" as passing;
    # under the pinned confusion set "5" <-> "9" is not a pair, so the
    # normative rules reject it (flagged to Ying, C1 2026-09-29).
    assert not is_ocr_confusion("125,000", "129,00O")


def test_cap_len6_rejects_second_replacement() -> None:
    # len 6 -> cap 1; two confusable mismatches exceed it.
    assert not is_ocr_confusion("1l0,0O", "110,00")


def test_length_diff_over_one_rejects() -> None:
    assert not is_ocr_confusion("12345", "12")
    assert not is_ocr_confusion("1", "12345")


def test_empty_inputs_reject() -> None:
    assert not is_ocr_confusion("", "1")
    assert not is_ocr_confusion("1", "")


def test_drop_tail_tried_before_drop_head() -> None:
    # Drop-tail aligns "1" with "1" -> pass (drop-head would pass too).
    assert is_ocr_confusion("12", "1")
    # Drop-tail "a" vs "1" fails (not confusable); drop-head "1" vs "1" passes.
    assert is_ocr_confusion("a1", "1")


def test_dropped_char_not_counted_as_replacement() -> None:
    # Long len 8 -> cap 2; drop-tail leaves 2 confusable mismatches. Counting
    # the dropped "9" would make 3 and fail.
    assert is_ocr_confusion("1l0,00O9", "110,000")


# --- P-002 C2: T1 anchored value match (pure solver tests) ---------------

def _w(x0, y0, x1, y1, text, block=0, line=0, word=0):
    return [x0, y0, x1, y1, text, block, line, word]


def _model(words, n_rows=1, n_cols=2, bbox=None):
    # default grid: raster 200x100 -> pt 100x50; cols [0,50]/[50,100]
    return build_layout_model(
        bbox or {"x": 0, "y": 0, "width": 200, "height": 100},
        words,
        n_rows,
        n_cols,
    )


def test_solve_t1_unique_when_row_and_column_anchor() -> None:
    model = _model([_w(10, 10, 40, 20, "1234")])
    status, words = solve_t1(model, "1234", 0, 0)  # center x=25 -> column 0
    assert status == T1Status.UNIQUE
    assert words is not None and words[0][4] == "1234"


def test_solve_t1_none_when_no_equal_run() -> None:
    model = _model([_w(10, 10, 40, 20, "1234")])
    assert solve_t1(model, "9999", 0, 0) == (T1Status.NONE, None)
    assert solve_t1(_model([]), "1234", 0, 0) == (T1Status.NONE, None)


def test_solve_t1_none_when_value_anchored_to_other_column() -> None:
    # Ying-2A regression anchor: unique value, but its word group anchors to
    # column 1 (center x=95 is outside column 0's expanded window [−30, 80]).
    model = _model([_w(90, 10, 100, 20, "1234")])
    assert solve_t1(model, "1234", 0, 0) == (T1Status.NONE, None)
    status, words = solve_t1(model, "1234", 0, 1)
    assert status == T1Status.UNIQUE


def test_solve_t1_collision_on_two_same_value_runs() -> None:
    model = _model(
        [_w(10, 10, 25, 20, "777", word=0), _w(60, 10, 75, 20, "777", word=1)]
    )
    assert solve_t1(model, "777", 0, 0) == (T1Status.COLLISION, None)


def test_resolve_t1_collision_unique_winner() -> None:
    model = _model(
        [_w(10, 10, 25, 20, "777", word=0), _w(60, 10, 75, 20, "777", word=1)]
    )
    ok, words = resolve_t1_collision(model, "777", 0, 0)
    assert ok and words[0][4] == "777" and words[0][0] == 10
    ok, words = resolve_t1_collision(model, "777", 0, 1)
    assert ok and words[0][0] == 60


def test_resolve_t1_collision_tie_is_ambiguous() -> None:
    # Both runs anchor to column 0 at the same distance -> no strict winner.
    model = _model(
        [_w(10, 10, 20, 20, "777", word=0), _w(30, 10, 40, 20, "777", word=1)]
    )
    assert resolve_t1_collision(model, "777", 0, 0) == (False, None)


# --- P-002 C3: T3 text-cluster mapping ------------------------------------

def test_solve_t3_provenance_literals_match_backfill_constants() -> None:
    # Drift guard: T3 returns wire-contract strings (no circular import).
    assert PROVENANCE_CONFIRMED_LITERAL == PROVENANCE_TEXT_CONFIRMED
    assert PROVENANCE_BACKFILLED_LITERAL == PROVENANCE_TEXT_BACKFILLED
    assert PROVENANCE_MISMATCH_LITERAL == PROVENANCE_TEXT_MISMATCH


def test_solve_t3_confirmed_cluster() -> None:
    words = [_w(10, 10, 40, 15, "12", line=0), _w(10, 15, 40, 20, "34", line=1)]
    model = _model(words, n_rows=1, n_cols=1)
    prov, reason, got = solve_t3(model, "1234", 0, 0, "multi_line")
    assert (prov, reason) == (PROVENANCE_TEXT_CONFIRMED, REASON_CLUSTER)
    assert [w[4] for w in got] == ["12", "34"]  # (cluster y1, x0) order


def test_solve_t3_backfilled_cluster() -> None:
    words = [_w(10, 10, 40, 15, "12", line=0), _w(10, 15, 40, 20, "34", line=1)]
    model = _model(words, n_rows=1, n_cols=1)
    prov, reason, got = solve_t3(model, "l234", 0, 0, "multi_line")
    assert (prov, reason) == (PROVENANCE_TEXT_BACKFILLED, REASON_CLUSTER)
    assert got


def test_solve_t3_sanity_reject_cluster() -> None:
    # "9234" vs "1234": 9 <-> 1 is not a pinned pair -> honest red, words kept.
    words = [_w(10, 10, 40, 15, "12", line=0), _w(10, 15, 40, 20, "34", line=1)]
    model = _model(words, n_rows=1, n_cols=1)
    prov, reason, got = solve_t3(model, "9234", 0, 0, "multi_line")
    assert (prov, reason) == (PROVENANCE_TEXT_MISMATCH, REASON_SANITY)
    assert got


def test_solve_t3_empty_set_keeps_t2_fail_reason() -> None:
    model = _model([], n_rows=1, n_cols=1)
    assert solve_t3(model, "1234", 0, 0, "crossing") == (
        PROVENANCE_TEXT_MISMATCH,
        "crossing",
        None,
    )
    assert solve_t3(model, "1234", 0, 0, "no_aligned_line") == (
        PROVENANCE_TEXT_MISMATCH,
        "no_aligned_line",
        None,
    )


def test_solve_t3_whitespace_only_words_keep_t2_fail_reason() -> None:
    model = _model([_w(10, 10, 40, 20, "   ")], n_rows=1, n_cols=1)
    assert solve_t3(model, "1234", 0, 0, "multi_line") == (
        PROVENANCE_TEXT_MISMATCH,
        "multi_line",
        None,
    )


# --- P-002 C3: layout model behaviors feeding T3 --------------------------

def test_row_cluster_tolerance_splits_beyond_row_tol() -> None:
    # heights 5 -> h_med 5 -> ROW_TOL 2.5: y1 diff 3 merges, diff 5 splits.
    merged = _model([_w(10, 10, 40, 20, "a"), _w(10, 13, 40, 23, "b", word=1)])
    split = _model([_w(10, 10, 40, 15, "a"), _w(10, 15, 40, 20, "b", word=1)])
    assert len(merged.row_clusters) == 1
    assert len(split.row_clusters) == 2


def test_in_row_group_split_on_gap() -> None:
    # x gap 10pt >= COL_GAP_PT=6 -> two word groups within one cluster.
    model = _model(
        [_w(10, 10, 40, 20, "12", word=0), _w(50, 10, 80, 20, "34", word=1)],
        n_rows=1,
        n_cols=1,
    )
    assert len(model.col_groups[0]) == 2


def test_cluster_row_tie_maps_to_lower_row() -> None:
    # Cluster band [20,30] overlaps both row bands by 5pt -> lower row wins.
    model = _model([_w(10, 20, 40, 30, "1234")], n_rows=2, n_cols=1)
    assert model.row_clusters[0].vision_row == 0


def test_unassigned_group_is_skipped_by_t3() -> None:
    # Narrow 5-col table (2pt cols): EXP_X = max(0.5, 1.2) = 1.2pt -> a word
    # centered in the left pad ring hits no column window -> unassigned, and
    # T3's collect skips it.
    model = _model(
        [_w(-5, 10, -2, 20, "A")],
        n_rows=1,
        n_cols=5,
        bbox={"x": 0, "y": 0, "width": 20, "height": 100},
    )
    assert model.col_groups[0][0].assigned_col is None
    assert collect_t3_words(model, 0, 0) == []
