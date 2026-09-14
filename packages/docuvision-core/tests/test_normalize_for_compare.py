"""Tests for normalize_for_compare (v1.8 §4.3)."""

from __future__ import annotations

from docuvision_core.utils.pdf_text_utils import normalize_for_compare


def test_nfkc_fullwidth_to_halfwidth() -> None:
    assert normalize_for_compare("ＡＢＣ１２３") == "ABC123"


def test_whitespace_removed() -> None:
    assert normalize_for_compare("1 234 567") == "1234567"
    assert normalize_for_compare("1\t234\n567") == "1234567"


def test_fullwidth_punctuation_folded() -> None:
    assert normalize_for_compare("１，２３４．５６") == "1,234.56"
    assert normalize_for_compare("（１２３）") == "(123)"


def test_none_becomes_empty() -> None:
    assert normalize_for_compare(None) == ""  # type: ignore[arg-type]


def test_identical_strings_normalize_equal() -> None:
    assert normalize_for_compare("1,234.56") == normalize_for_compare("１，２３４．５６")


def test_symbols_preserved() -> None:
    assert normalize_for_compare("✓⊗●○") == "✓⊗●○"
