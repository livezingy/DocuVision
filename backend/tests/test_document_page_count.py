from unittest.mock import patch

from app.services.document_info_utils import resolve_document_page_count


def test_resolve_document_page_count_prefers_pdf_file(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    result = {"document_info": {"pages": 0}, "layout": {"total_pages": 1}}
    with patch("app.services.document_info_utils.pdf_page_count", return_value=3):
        assert resolve_document_page_count(str(pdf), result) == 3


def test_resolve_document_page_count_from_layout_when_not_pdf(tmp_path):
    png = tmp_path / "scan.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    result = {"document_info": {"pages": 0}, "layout": {"total_pages": 2}}
    assert resolve_document_page_count(str(png), result) == 2


def test_resolve_document_page_count_from_view_pages():
    result = {
        "document_info": {"pages": 0},
        "view": {"pages": [{"page_num": 1}, {"page_num": 2}, {"page_num": 3}]},
    }
    assert resolve_document_page_count("/tmp/x.pdf", result) == 3


def test_resolve_document_page_count_defaults_to_one():
    assert resolve_document_page_count("/tmp/x.png", {}) == 1
