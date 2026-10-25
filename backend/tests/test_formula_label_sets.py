"""
P-040 ② anti-drift sentinel for the formula-region label set.

Sites that must agree on which layout labels are formula regions:
  - steps/extraction.py FORMULA_LAYOUT_TYPES (ROI collection in formula_step)
  - EnvelopeBuilder.SKIP_FORMULA_TYPES (status classification + envelope merge filter)
They must be the same object, and every member must map to view kind "formula".
formula_number must NOT sit in _OCR_TEXT_LABELS — it left the OCR-text path in this
batch; a relapse would silently resurrect the numbered-formula-as-garbage-text
behavior (official PP-StructureV3 crops formula_number boxes into FormulaNet
instead, see docs/architecture/pp-structurev3-official-findings.md).
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.orchestration.envelope_builder import EnvelopeBuilder
from app.orchestration.envelope_builder_helpers import _map_block_type_to_kind
from app.orchestration.steps.extraction import FORMULA_LAYOUT_TYPES

EXPECTED_FORMULA_TYPES = {"formula", "inline_formula", "equation", "formula_number"}


def test_skip_formula_types_membership():
    assert EnvelopeBuilder.SKIP_FORMULA_TYPES == EXPECTED_FORMULA_TYPES


def test_extraction_accepted_is_skip_set():
    assert FORMULA_LAYOUT_TYPES is EnvelopeBuilder.SKIP_FORMULA_TYPES


def test_every_skip_type_maps_to_formula_kind():
    for t in EnvelopeBuilder.SKIP_FORMULA_TYPES:
        assert _map_block_type_to_kind(t) == "formula", t


def test_formula_number_left_ocr_text_path():
    assert "formula_number" not in EnvelopeBuilder._OCR_TEXT_LABELS
    # "number" (page number) stays an OCR-text label.
    assert "number" in EnvelopeBuilder._OCR_TEXT_LABELS


def test_number_kind_unchanged():
    assert _map_block_type_to_kind("number") == "number"
