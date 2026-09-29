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
    is_ocr_confusion,
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
