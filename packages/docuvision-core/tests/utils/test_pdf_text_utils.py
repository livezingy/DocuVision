"""Tests for PDF text cleanup utilities."""

from docuvision_core.utils.pdf_text_utils import decode_cid_placeholders, sanitize_pdf_text


def test_decode_cid_utf8_em_dash():
    raw = "(cid:226)(cid:128)(cid:148)"
    assert decode_cid_placeholders(raw) == "\u2014"


def test_decode_cid_leaves_plain_text():
    assert decode_cid_placeholders("ACH OUT - PAYROLL") == "ACH OUT - PAYROLL"


def test_sanitize_pdf_text_strips_cid_and_whitespace():
    raw = "  (cid:226)(cid:128)(cid:148)  memo  "
    assert sanitize_pdf_text(raw) == "\u2014 memo"
