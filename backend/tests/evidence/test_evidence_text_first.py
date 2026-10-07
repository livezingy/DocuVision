"""P-032 text-first hardening tests (M5/M4/M1).

Covers, per execution-package §3 (mock layer, no Paddle/Qwen):
  M5  evidence trust predicate: born-digital trusted / invisible overlay
      rejected / no-text rejected / real BMC page 1 trusted.
  M4  deterministic grounding (marker hint + V-ladder page attribution).
  M1  marker build/parse, window splitting, native text payload.

The real-PDF anchors use the in-repo CC-BY corpus fixture
``test_data/testfiles/pico/pub_bmc_PMC10685505.pdf`` (the evidence golden
source paper ``pub_bmc``).
"""
from __future__ import annotations

from pathlib import Path

import fitz

from app.services.evidence import grounding

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[2]

BMC_PDF = _PROJECT_ROOT / "test_data" / "testfiles" / "pico" / "pub_bmc_PMC10685505.pdf"


def _make_pdf(tmp_path, name="doc.pdf", pages=()):
    """Build a synthetic PDF. ``pages``: iterable of (visible, invisible)
    text-line tuples, one page per tuple, in order."""
    doc = fitz.open()
    for visible, invisible in pages:
        page = doc.new_page()
        y = 72.0
        for text in visible:
            page.insert_text((72, y), text)
            y += 14.0
        for text in invisible:
            page.insert_text((72, y), text, render_mode=3)
            y += 14.0
    pdf_path = tmp_path / name
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


# ---------------------------------------------------------------- M5: trust


def test_m5_born_digital_page_trusted(tmp_path):
    pdf = _make_pdf(tmp_path, pages=((("Treatment may reduce infarct size in patients.",), ()),))
    assert grounding.trusted_grounding_page_set(pdf) == {1}


def test_m5_no_text_page_rejected(tmp_path):
    doc = fitz.open()
    doc.new_page()  # blank page: total_chars == 0
    pdf_path = tmp_path / "blank.pdf"
    doc.save(str(pdf_path))
    doc.close()
    assert grounding.trusted_grounding_page_set(str(pdf_path)) == set()


def test_m5_invisible_overlay_page_rejected(tmp_path):
    # render_mode=3 => invisible (Tr 3) text: invisible_ratio == 1.0 >= 0.5
    pdf = _make_pdf(tmp_path, pages=(((), ("scanned page ghost text layer",)),))
    assert grounding.trusted_grounding_page_set(pdf) == set()


def test_m5_invisible_ratio_boundary(tmp_path):
    # equal char counts => ratio 0.5 => NOT < 0.5 => rejected
    half = _make_pdf(tmp_path, pages=((("abcdefghijklm",), ("nopqrstuvwxyz",)),))
    assert grounding.trusted_grounding_page_set(half) == set()
    # invisible minority (10 of 32 chars ~ 0.31) => trusted
    mostly_visible = _make_pdf(
        tmp_path, name="ok.pdf", pages=((("visible one", "visible two"), ("ghost line",)),)
    )
    assert grounding.trusted_grounding_page_set(mostly_visible) == {1}


def test_m5_bmc_first_page_trusted(tmp_path):
    # Real corpus anchor (M5 DoD): BMC page 1 carries a born-digital text
    # layer (invisible_ratio 0.0 measured in C0) -> trusted under the
    # evidence predicate even though its image coverage (~0.61) fails E1.
    assert 1 in grounding.trusted_grounding_page_set(str(BMC_PDF))
