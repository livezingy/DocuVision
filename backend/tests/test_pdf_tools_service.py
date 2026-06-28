"""Unit tests for PDF tools helpers (no PyMuPDF required)."""

from app.services.pdf_tools_service import coerce_page_list


def test_coerce_page_list_single_int():
    assert coerce_page_list(1) == [1]


def test_coerce_page_list_json_int_like():
    assert coerce_page_list(3) == [3]


def test_coerce_page_list_list():
    assert coerce_page_list([1, 2, 3]) == [1, 2, 3]


def test_coerce_page_list_empty_list():
    assert coerce_page_list([]) is None


def test_coerce_page_list_none():
    assert coerce_page_list(None) is None
