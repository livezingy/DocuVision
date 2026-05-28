"""Tests for PDF text paragraph preservation."""

from docuvision_core.utils.pdf_text_utils import normalize_pdf_text_preserve_paragraphs


def test_normalize_pdf_text_preserve_paragraphs_keeps_blank_line_breaks():
    raw = "First paragraph line one\nline two\n\nSecond paragraph"
    result = normalize_pdf_text_preserve_paragraphs(raw)
    assert result == "First paragraph line one\nline two\n\nSecond paragraph"


def test_normalize_pdf_text_collapse_within_line():
    from docuvision_core.utils.pdf_text_utils import sanitize_pdf_text

    assert sanitize_pdf_text("too   many   spaces") == "too many spaces"
