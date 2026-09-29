"""Unit tests for table_alignment (P-002 C1): reason contract + sanity gate.

Pure logic — no fitz, no paddle, no server (testing.md local layer).
"""

from __future__ import annotations

from app.services.table_alignment import (
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
    is_ocr_confusion,
    resolve_t1_collision,
    solve_t1,
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
    )
    assert len(set(REASON_KEYS)) == 8


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
