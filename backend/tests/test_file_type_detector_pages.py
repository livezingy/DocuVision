"""Tests for per-page file type detection (v1.8 §3.3)."""

from __future__ import annotations

import fitz

from app.services.file_type_detector import (
    DetectedFileType,
    detect_file_type,
    detect_file_type_pages,
)


def _add_text_page(doc) -> None:
    page = doc.new_page()
    font = fitz.Font("helv")
    tw = fitz.TextWriter(page.rect)
    tw.append((50, 80), "born digital page text", font=font, fontsize=11)
    tw.write_text(page)


def _add_overlay_page(doc) -> None:
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), 0)
    pix.clear_with(255)
    page.insert_image(page.rect, stream=pix.tobytes("png"))
    page.insert_text((50, 80), "invisible overlay text", fontsize=11, render_mode=3)


def _write(doc, path) -> None:
    doc.save(path)
    doc.close()


def test_mixed_pdf_per_page_verdicts(tmp_path) -> None:
    path = str(tmp_path / "mixed.pdf")
    doc = fitz.open()
    _add_text_page(doc)
    _add_overlay_page(doc)
    _write(doc, path)

    info = detect_file_type_pages(path)
    assert info["page_count"] == 2
    assert info["page_types"] == ["digital", "scan"]
    assert info["page_verdicts"] == ["text_layer", "overlay"]
    assert info["born_digital"] is False


def test_digital_pdf_born_digital_true(tmp_path) -> None:
    path = str(tmp_path / "digital.pdf")
    doc = fitz.open()
    _add_text_page(doc)
    _write(doc, path)

    info = detect_file_type_pages(path)
    assert info["born_digital"] is True
    detected, pages = detect_file_type(path)
    assert detected == DetectedFileType.PDF_DIGITAL
    assert pages == 1


def test_scan_pdf_born_digital_false(tmp_path) -> None:
    path = str(tmp_path / "scan.pdf")
    doc = fitz.open()
    _add_overlay_page(doc)
    _write(doc, path)

    info = detect_file_type_pages(path)
    assert info["born_digital"] is False
    detected, pages = detect_file_type(path)
    assert detected == DetectedFileType.PDF_SCAN
    assert pages == 1
