"""Unit tests for PDF tools helpers.

P-046 package A: the service was migrated fitz -> pypdf. Fixtures are
*created* with PyMuPDF (fitz, test-only dependency per the repo's fitz
discipline) and every verification *reads back* with pypdf (the
production library pinned in backend/requirements.txt).
"""

import os
from typing import List

import fitz  # test-only: fixture creation
import pytest
from pypdf import PdfReader

from app.services.pdf_tools_service import (
    coerce_page_list,
    fill_acroform,
    merge_pdfs,
    read_pdf_metadata,
    split_pdf,
)


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


# ---------------------------------------------------------------- fixtures


def _make_text_pdf(path: str, page_texts: List[str], metadata: dict = None) -> str:
    """Create a multi-page PDF with one marker text per page (via fitz)."""
    doc = fitz.open()
    for text in page_texts:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=14)
    if metadata:
        doc.set_metadata(metadata)
    doc.save(path)
    doc.close()
    return path


def _make_acroform_pdf(path: str, field_names: List[str]) -> str:
    """Create a PDF with AcroForm text fields (via fitz)."""
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for name in field_names:
        widget = fitz.Widget()
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.field_name = name
        widget.field_value = ""
        widget.rect = fitz.Rect(50, y, 250, y + 24)
        page.add_widget(widget)
        y += 40
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def two_pdfs(tmp_path):
    a = _make_text_pdf(
        str(tmp_path / "a.pdf"),
        ["MERGE-A-PAGE-1", "MERGE-A-PAGE-2"],
    )
    b = _make_text_pdf(
        str(tmp_path / "b.pdf"),
        ["MERGE-B-PAGE-1", "MERGE-B-PAGE-2"],
    )
    return a, b


@pytest.fixture
def three_page_pdf(tmp_path):
    return _make_text_pdf(
        str(tmp_path / "three.pdf"),
        ["SPLIT-PAGE-1", "SPLIT-PAGE-2", "SPLIT-PAGE-3"],
    )


@pytest.fixture
def acroform_pdf(tmp_path):
    return _make_acroform_pdf(str(tmp_path / "form.pdf"), ["full_name", "email"])


# ---------------------------------------------------------------- merge


class TestMergePdfs:
    def test_merged_page_count(self, two_pdfs, tmp_path):
        out = str(tmp_path / "merged.pdf")
        result = merge_pdfs(list(two_pdfs), out)
        assert result == out
        assert os.path.isfile(out)
        reader = PdfReader(out)
        assert len(reader.pages) == 4

    def test_merged_content_order(self, two_pdfs, tmp_path):
        out = str(tmp_path / "merged.pdf")
        merge_pdfs(list(two_pdfs), out)
        text = PdfReader(out).pages[0].extract_text()
        assert "MERGE-A-PAGE-1" in text

    def test_single_input(self, two_pdfs, tmp_path):
        out = str(tmp_path / "merged_one.pdf")
        merge_pdfs([two_pdfs[0]], out)
        assert len(PdfReader(out).pages) == 2


# ---------------------------------------------------------------- split


class TestSplitPdf:
    def test_split_all_pages(self, three_page_pdf, tmp_path):
        out_dir = str(tmp_path / "out_all")
        outputs = split_pdf(three_page_pdf, out_dir)
        assert len(outputs) == 3
        assert [os.path.basename(p) for p in outputs] == [
            "page_1.pdf",
            "page_2.pdf",
            "page_3.pdf",
        ]
        for i, path in enumerate(outputs, start=1):
            reader = PdfReader(path)
            assert len(reader.pages) == 1
            assert f"SPLIT-PAGE-{i}" in reader.pages[0].extract_text()

    def test_split_selected_pages(self, three_page_pdf, tmp_path):
        out_dir = str(tmp_path / "out_sel")
        outputs = split_pdf(three_page_pdf, out_dir, pages=[2])
        assert outputs == [os.path.join(out_dir, "page_2.pdf")]
        text = PdfReader(outputs[0]).pages[0].extract_text()
        assert "SPLIT-PAGE-2" in text
        assert "SPLIT-PAGE-1" not in text

    def test_split_skips_out_of_range(self, three_page_pdf, tmp_path):
        out_dir = str(tmp_path / "out_bounds")
        # 0 and 99 are out of the 1..3 range -> skipped, not an error
        outputs = split_pdf(three_page_pdf, out_dir, pages=[0, 99, 2])
        assert [os.path.basename(p) for p in outputs] == ["page_2.pdf"]

    def test_split_junk_entries_coerced(self, three_page_pdf, tmp_path):
        out_dir = str(tmp_path / "out_junk")
        outputs = split_pdf(three_page_pdf, out_dir, pages=["1", "x", 3])
        assert [os.path.basename(p) for p in outputs] == ["page_1.pdf", "page_3.pdf"]


class TestCoercePageListExtra:
    def test_list_with_junk(self):
        assert coerce_page_list([1, "2", "x", None]) == [1, 2]

    def test_non_list_non_int(self):
        assert coerce_page_list("12") is None


# ---------------------------------------------------------------- metadata


class TestReadPdfMetadata:
    def test_top_level_keys_and_page_count(self, three_page_pdf):
        info = read_pdf_metadata(three_page_pdf)
        assert set(info.keys()) == {"page_count", "metadata"}
        assert info["page_count"] == 3

    def test_metadata_keys_pypdf_style(self, tmp_path):
        path = _make_text_pdf(
            str(tmp_path / "meta.pdf"),
            ["META-PAGE-1"],
            metadata={
                "title": "DocuVision Title",
                "author": "DocuVision Author",
                "subject": "DocuVision Subject",
                "creator": "DocuVision Creator",
                "producer": "DocuVision Producer",
            },
        )
        meta = read_pdf_metadata(path)["metadata"]
        # pypdf key names (fitz used creationDate/modDate; pypdf uses
        # creation_date/modification_date — registered acceptable deviation)
        assert meta["title"] == "DocuVision Title"
        assert meta["author"] == "DocuVision Author"
        assert meta["subject"] == "DocuVision Subject"
        assert meta["creator"] == "DocuVision Creator"
        assert meta["producer"] == "DocuVision Producer"

    def test_metadata_absent_keys_omitted(self, three_page_pdf):
        meta = read_pdf_metadata(three_page_pdf)["metadata"]
        assert isinstance(meta, dict)
        # keys without a value in the Info dict are omitted (fitz filled
        # empty strings; pypdf returns None -> omitted)
        assert "creation_date" not in meta
        assert "modification_date" not in meta

    def test_metadata_values_json_safe(self, tmp_path):
        path = _make_text_pdf(
            str(tmp_path / "meta2.pdf"), ["P1"], metadata={"title": "Té"}
        )
        meta = read_pdf_metadata(path)["metadata"]
        assert meta["title"] == "Té"
        assert all(isinstance(v, str) for v in meta.values())


# ---------------------------------------------------------------- acroform


class TestFillAcroform:
    def test_filled_values_readable_back(self, acroform_pdf, tmp_path):
        out = str(tmp_path / "filled.pdf")
        result = fill_acroform(acroform_pdf, out, {"full_name": "张三", "email": "a@b.c"})
        assert result == out
        fields = PdfReader(out).get_fields()
        assert str(fields["full_name"]["/V"]) == "张三"
        assert str(fields["email"]["/V"]) == "a@b.c"

    def test_need_appearances_flag_set(self, acroform_pdf, tmp_path):
        out = str(tmp_path / "filled_na.pdf")
        fill_acroform(acroform_pdf, out, {"full_name": "x"})
        acroform = PdfReader(out).trailer["/Root"]["/AcroForm"]
        # value is pypdf BooleanObject(True), not the literal True singleton
        need_appearances = acroform.get("/NeedAppearances")
        assert need_appearances is not None
        assert bool(need_appearances)

    def test_unknown_field_name_no_crash(self, acroform_pdf, tmp_path):
        out = str(tmp_path / "filled_unknown.pdf")
        result = fill_acroform(acroform_pdf, out, {"nonexistent_field": "v"})
        assert result == out
        assert os.path.isfile(out)

    def test_pdf_without_acroform(self, three_page_pdf, tmp_path):
        out = str(tmp_path / "no_form_out.pdf")
        result = fill_acroform(three_page_pdf, out, {"full_name": "v"})
        assert result == out
        assert len(PdfReader(out).pages) == 3

    def test_non_targeted_field_untouched(self, acroform_pdf, tmp_path):
        out = str(tmp_path / "filled_partial.pdf")
        fill_acroform(acroform_pdf, out, {"full_name": "only-name"})
        fields = PdfReader(out).get_fields()
        assert str(fields["full_name"]["/V"]) == "only-name"
        email_value = fields["email"].get("/V")
        assert email_value in (None, "")
