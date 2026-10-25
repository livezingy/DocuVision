"""Shared-leaf contract tests (runs/split batch 2, P-037/P-038).

Mock/pure only — no Paddle, no server. Covers the two leaves promoted to
break the evidence<->kie and hitl<->kie cycles:
  * ``text_first_contract``: flag-parameterized predicates + marker/payload
    format + body-page rule (promoted verbatim; the settings read stays with
    the kie.text_first wrappers, verified here by monkeypatching settings).
  * ``kie_default_rules``: the document-type -> default-rules mapping must be
    the SAME object through both import paths (leaf and the field_validation
    re-export) — hitl and kie can never drift.
  * ``build_text_first_payloads``: the injected-grounding contract (L2 passes
    evidence.grounding results in; no kie->evidence import).
"""

from __future__ import annotations

from app.services.kie import text_first as tf
from app.services.kie.field_validation import (
    default_rules_for_document_type as rules_via_field_validation,
)
from app.services.kie_default_rules import default_rules_for_document_type
from app.services.text_first_contract import (
    block_marker,
    text_first_enabled,
    text_first_from_ctx,
)


def test_leaf_text_first_enabled_truth_table():
    assert text_first_enabled("pico", True, flag=True) is True
    assert text_first_enabled("pico", True, flag=False) is False  # flag off -> legacy
    assert text_first_enabled("invoice", True, flag=True) is False  # M1 side
    assert text_first_enabled("pico", False, flag=True) is False  # non-PDF


def test_leaf_text_first_from_ctx_resolves_metadata():
    ctx = {
        "file_path": "/tmp/a.PDF",
        "result": {"kie_meta": {"resolved_document_type": "pico"}},
    }
    assert text_first_from_ctx(ctx, flag=True) is True
    assert text_first_from_ctx(ctx, flag=False) is False
    assert text_first_from_ctx({"result": {"kie_meta": {}}}, flag=True) is False


def test_kie_wrapper_reads_settings(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "EVIDENCE_TEXT_FIRST", True, raising=False)
    assert tf.text_first_enabled("pico", is_pdf=True) is True
    assert tf.text_first_from_ctx(
        {"file_path": "x.pdf", "result": {"kie_meta": {"resolved_document_type": "pico"}}}
    ) is True
    monkeypatch.setattr(settings, "EVIDENCE_TEXT_FIRST", False, raising=False)
    assert tf.text_first_enabled("pico", is_pdf=True) is False


def test_marker_format_unchanged():
    assert block_marker(5, 0) == "[p5_b0]"
    assert tf.build_page_payload(["alpha", "beta"], 5) == (
        f"{block_marker(5, 0)} alpha\n{block_marker(5, 1)} beta"
    )


def test_default_rules_single_source_of_truth():
    assert default_rules_for_document_type is rules_via_field_validation
    assert default_rules_for_document_type("invoice")["total"] == {"type": "currency"}
    assert default_rules_for_document_type("id_card")["id_number"]["pattern"] == r"^\d{18}$"
    assert default_rules_for_document_type("unknown-type") == {}


def test_build_payloads_injected_grounding_contract():
    """The grounding layer is injected by the orchestrator's KIE step (batch 3):
    kie.text_first carries no evidence import at all — the one-way frozen edge
    is gone; the payload branches are verified here with plain dict inputs."""
    layout = {"elements": [
        {"page": 2, "type": "text", "text": "ocr text for page two"},
    ]}
    payloads = tf.build_text_first_payloads(
        layout,
        [1, 2, 3],
        blocks_by_page={1: ["born digital body text for page one"]},
        trusted_pages={1},
    )
    assert payloads[1]["source"] == tf.SOURCE_TEXT_LAYER
    assert "[p1_b0]" in payloads[1]["windows"][0]
    assert payloads[2]["source"] == tf.SOURCE_FUSED_OCR  # declared fallback (R3)
    assert "[p2_b0] ocr text for page two" in payloads[2]["windows"]
    assert 3 not in payloads  # no text anywhere -> image channel (visible by absence)
