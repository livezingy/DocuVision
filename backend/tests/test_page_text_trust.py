"""Tests for the E1 page-level text-layer trust gatekeeper.

Synthesises two fixture classes in-test (no external assets, only PyMuPDF):
  * real text layer (visible text, no image)      -> trusted / text_layer
  * OCR overlay layer (full-page image + Tr3 text) -> overlay (confidence=1.0)
  * ambiguous (full-page image + visible text)     -> mixed / untrusted
"""

from __future__ import annotations

import fitz

from app.services.page_text_trust import judge_page_trust


def _make_text_layer_pdf(path) -> None:
    """Real born-digital page: visible text, no image."""
    doc = fitz.open()
    page = doc.new_page()
    font = fitz.Font("helv")
    tw = fitz.TextWriter(page.rect)
    tw.append((50, 80), "Hello trusted text layer 123.45", font=font, fontsize=11)
    tw.append((50, 100), "Second visible line ABC", font=font, fontsize=11)
    tw.write_text(page)
    doc.save(path)
    doc.close()


def _make_overlay_pdf(path) -> None:
    """Scanned page + OCR overlay: full-page image + invisible (Tr3) text."""
    doc = fitz.open()
    page = doc.new_page()
    # Full-page image (drives image_coverage >= 0.8).
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), 0)
    pix.clear_with(255)
    png = pix.tobytes("png")
    page.insert_image(page.rect, stream=png)
    # Invisible text via render mode 3 (Tr3).
    page.insert_text((50, 80), "invisible ocr text layer", fontsize=11, render_mode=3)
    page.insert_text((50, 100), "more invisible glyphs", fontsize=11, render_mode=3)
    doc.save(path)
    doc.close()


def _make_mixed_pdf(path) -> None:
    """Ambiguous: full-page image + visible text (not clearly trusted)."""
    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), 0)
    pix.clear_with(255)
    page.insert_image(page.rect, stream=pix.tobytes("png"))
    font = fitz.Font("helv")
    tw = fitz.TextWriter(page.rect)
    tw.append((50, 80), "visible text on top of a full-page image", font=font, fontsize=11)
    tw.write_text(page)
    doc.save(path)
    doc.close()


def _open_page(path):
    doc = fitz.open(path)
    try:
        return doc[0], doc
    except Exception:
        doc.close()
        raise


def test_real_text_layer_is_trusted(tmp_path) -> None:
    path = str(tmp_path / "digital.pdf")
    _make_text_layer_pdf(path)
    page, doc = _open_page(path)
    try:
        result = judge_page_trust(page)
        assert result.trusted is True
        assert result.verdict == "text_layer"
        assert result.signals["invisible_ratio"] < 0.2
        assert result.signals["image_coverage"] < 0.5
    finally:
        doc.close()


def test_ocr_overlay_is_rejected(tmp_path) -> None:
    path = str(tmp_path / "overlay.pdf")
    _make_overlay_pdf(path)
    page, doc = _open_page(path)
    try:
        result = judge_page_trust(page)
        assert result.trusted is False
        assert result.verdict == "overlay"
        assert result.confidence == 1.0
        assert result.signals["invisible_ratio"] >= 0.5
        assert result.signals["image_coverage"] >= 0.8
    finally:
        doc.close()


def test_ambiguous_page_is_untrusted(tmp_path) -> None:
    path = str(tmp_path / "mixed.pdf")
    _make_mixed_pdf(path)
    page, doc = _open_page(path)
    try:
        result = judge_page_trust(page)
        assert result.trusted is False
        assert result.verdict == "mixed"
    finally:
        doc.close()


def test_blank_page_is_no_text(tmp_path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    path = str(tmp_path / "blank.pdf")
    doc.save(path)
    doc.close()
    page2, doc2 = _open_page(path)
    try:
        result = judge_page_trust(page2)
        assert result.trusted is False
        assert result.verdict == "no_text"
        assert result.signals["total_chars"] == 0
    finally:
        doc2.close()
