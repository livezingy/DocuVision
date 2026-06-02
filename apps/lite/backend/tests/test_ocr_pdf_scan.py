"""Tests for scanned PDF OCR rasterization path."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.schemas.lite_result import DetectedFileType
from app.services.ocr_pipeline import _is_pdf, _load_images_from_path


def test_is_pdf_by_extension(tmp_path: Path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 minimal")
    assert _is_pdf(pdf) is True


def test_is_pdf_by_magic(tmp_path: Path):
    bin_file = tmp_path / "scan.bin"
    bin_file.write_bytes(b"%PDF-1.4")
    assert _is_pdf(bin_file) is True


@patch("app.services.page_utils.fitz")
def test_load_images_from_pdf(mock_fitz, tmp_path: Path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    mock_page = MagicMock()
    mock_pix = MagicMock()
    mock_pix.n = 3
    mock_pix.width = 10
    mock_pix.height = 10
    mock_pix.samples = bytes([255] * 300)
    mock_page.get_pixmap.return_value = mock_pix

    mock_doc = MagicMock()
    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.return_value = mock_page
    mock_fitz.open.return_value.__enter__.return_value = mock_doc
    mock_fitz.Matrix.return_value = MagicMock()

    pages = _load_images_from_path(pdf, page_count=1, max_pages=1)
    assert len(pages) == 1
    assert pages[0][0] == 1
    assert isinstance(pages[0][1], Image.Image)


@patch("app.services.page_utils.fitz")
def test_extract_ocr_from_image_accepts_pdf(mock_fitz, tmp_path: Path):
    from app.services.ocr_pipeline import extract_ocr_from_image

    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    mock_page = MagicMock()
    mock_pix = MagicMock()
    mock_pix.n = 3
    mock_pix.width = 20
    mock_pix.height = 20
    mock_pix.samples = bytes([255] * 1200)
    mock_page.get_pixmap.return_value = mock_pix
    mock_doc = MagicMock()
    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.return_value = mock_page
    mock_fitz.open.return_value.__enter__.return_value = mock_doc
    mock_fitz.Matrix.return_value = MagicMock()

    with patch(
        "app.services.file_detector.detect_file_type",
        return_value=(DetectedFileType.PDF_SCAN, 1),
    ):
        with patch("app.services.ocr_pipeline._run_tesseract", return_value=[]):
            with patch("app.services.ocr_pipeline._resolve_ocr_engine", return_value="tesseract"):
                with patch("shutil.which", return_value="/usr/bin/tesseract"):
                    out = extract_ocr_from_image(pdf, engine="tesseract")
    assert out["quality"]["pages_processed"] == 1
    assert any(w.get("code") == "scan_detected" for w in out.get("warnings", []))
