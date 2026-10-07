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

import asyncio

import fitz

from app.core.config import settings
from app.services.evidence import gate, grounding
from app.services.evidence.grounding import (
    GroundingSource,
    attribute_candidates,
    grounding_source,
    parse_marker_page,
)
from app.services.hitl_queue import HitlReviewQueue

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


# ------------------------------------------------- M4: marker parse + attribute


def _source(pages):
    """GroundingSource from {page: [block texts]}."""
    blocks = {p: list(texts) for p, texts in pages.items()}
    texts = {p: " ".join("\n".join(t).split()) for p, t in blocks.items()}
    return GroundingSource(blocks=blocks, texts=texts)


def test_m4_parse_marker_page():
    assert parse_marker_page("[p5_b12]") == 5
    assert parse_marker_page("[p23_b0]") == 23
    assert parse_marker_page("  [p3_b7]  ") == 3
    assert parse_marker_page(7) is None  # legacy integer shape: ignored
    assert parse_marker_page("block 7") is None
    assert parse_marker_page(None) is None
    assert parse_marker_page("") is None


def _candidate(quote, **overrides):
    candidate = {
        "statement": "statement of " + quote[:20],
        "statement_type": "original_finding",
        "quote": quote,
        "population": "p",
        "intervention": "i",
        "comparator": "c",
        "outcome": "o",
        "followup": "f",
    }
    candidate.update(overrides)
    return candidate


def test_m4_marker_hint_hit_attributes_page():
    source = _source({1: ["intro text"], 2: ["the result was significant overall"]})
    candidates = [
        _candidate("the result was significant overall", quote_block="[p2_b0]")
    ]
    out, stats = attribute_candidates(candidates, source)
    assert out[0]["page"] == 2
    assert stats["marker_hint_hits"] == 1 and stats["scan_hits"] == 0


def test_m4_false_marker_corrected_by_scan():
    # R4: model cites a wrong marker -> deterministic ladder scan wins.
    source = _source({1: ["intro text"], 2: ["the result was significant overall"]})
    candidates = [
        _candidate("the result was significant overall", quote_block="[p1_b0]")
    ]
    out, stats = attribute_candidates(candidates, source)
    assert out[0]["page"] == 2
    assert stats["scan_hits"] == 1 and stats["marker_hint_hits"] == 0


def test_m4_multipage_ambiguity_lowest_page_wins():
    repeated = "the same sentence appears twice"
    source = _source({1: [repeated], 2: [repeated, "more"]})
    out, stats = attribute_candidates([_candidate(repeated)], source)
    assert out[0]["page"] == 1
    assert stats["scan_hits"] == 1


def test_m4_no_verbatim_hit_prefix_page_fail_closed():
    # Quote absent verbatim (long tail drops the prefix ratio below 0.90) ->
    # best-prefix page so Gate A emits the pinned "N/Mw prefix" detail, never
    # "grounding unavailable" (E2 shape).
    body = "patients received phosphocreatine or placebo before surgery"
    source = _source({1: [body]})
    out, stats = attribute_candidates(
        [_candidate(body + " today and tomorrow")],
        source,
    )
    assert out[0]["page"] == 1 and stats["prefix_only"] == 1
    report = gate.verify_candidates(out, source.texts, {1}, "doc.pdf")
    assert report.rejected == 1
    assert report.ledger[0]["detail"].endswith("w prefix")
    assert "grounding unavailable" not in report.ledger[0]["detail"]


def test_m4_existing_page_untouched_and_empty_source_unresolved():
    candidates = [_candidate("anything", page=3)]
    out, stats = attribute_candidates(candidates, _source({1: ["text"]}))
    assert out[0]["page"] == 3 and stats == {
        "marker_hint_hits": 0,
        "scan_hits": 0,
        "prefix_only": 0,
        "unresolved": 0,
    }
    out2, stats2 = attribute_candidates([_candidate("anything")], GroundingSource(blocks={}, texts={}))
    assert "page" not in out2[0] and stats2["unresolved"] == 1


def test_m4_grounding_source_from_real_pdf(tmp_path):
    # Same-source property: the M1 payload builder and M4 grounding read the
    # same extraction; blocks are non-empty and texts join them normalized.
    source = grounding_source(str(BMC_PDF))
    assert source.blocks.get(1) and source.texts.get(1)
    assert "Lomivorotov" in source.texts[1]


# --------------------------------------------- M4: gate wiring (flag branches)


def _gate_ctx(tmp_path, pdf, candidates):
    return {
        "task_id": "t1",
        "task": {"file_name": "paper.pdf"},
        "file_path": str(pdf),
        "result": {
            "kie_fields": {"findings": candidates},
            "kie_fields_by_page": {"1": {"findings": candidates}},
            "kie_meta": {"kie_pages_processed": [1]},
        },
    }


def test_m4_gate_text_first_branch_end_to_end(tmp_path, monkeypatch):
    quote = "Treatment may reduce infarct size in patients."
    pdf = _make_pdf(tmp_path, pages=((("Before it. " + quote + " After it.",), ()),))
    monkeypatch.setattr(settings, "EVIDENCE_ENABLED", True)
    monkeypatch.setattr(settings, "EVIDENCE_TEXT_FIRST", True)
    import app.services.hitl_queue as hq_module

    monkeypatch.setattr(hq_module, "hitl_queue", HitlReviewQueue())
    block = asyncio.run(gate.run_evidence_gate(_gate_ctx(tmp_path, pdf, [_candidate(quote)])))
    assert block["findings"], block
    record = block["findings"][0]
    assert record["source"]["page_num"] == 1
    assert record["verdict"] == "verbatim_exact"
    assert record["quote_span"]
    assert block["export_allowed"] is True
    assert block["stats"]["page_injected"] == 1
    assert block["stats"]["marker_hint_hits"] + block["stats"]["scan_hits"] == 1
    assert block["stats"]["trusted_pages"] == [1]


def test_m4_gate_text_first_absent_quote_prefix_detail(tmp_path, monkeypatch):
    pdf = _make_pdf(tmp_path, pages=((("Some unrelated body text lives here.",), ()),))
    monkeypatch.setattr(settings, "EVIDENCE_ENABLED", True)
    monkeypatch.setattr(settings, "EVIDENCE_TEXT_FIRST", True)
    import app.services.hitl_queue as hq_module

    monkeypatch.setattr(hq_module, "hitl_queue", HitlReviewQueue())
    block = asyncio.run(gate.run_evidence_gate(_gate_ctx(
        tmp_path, pdf, [_candidate("a totally absent quote about nothing at all")])))
    assert block["export_allowed"] is False
    ledger = block["failure_ledger"][0]
    assert ledger["detail"].endswith("w prefix")
    assert "grounding unavailable" not in ledger["detail"]


def test_m4_gate_flag_off_keeps_legacy_branch(tmp_path, monkeypatch):
    # E6 (mock face): flag off -> legacy enrich path, zero new behavior.
    quote = "Treatment may reduce infarct size in patients."
    pdf = _make_pdf(tmp_path, pages=((("Before it. " + quote + " After it.",), ()),))
    monkeypatch.setattr(settings, "EVIDENCE_ENABLED", True)
    monkeypatch.setattr(settings, "EVIDENCE_TEXT_FIRST", False)
    import app.services.hitl_queue as hq_module

    monkeypatch.setattr(hq_module, "hitl_queue", HitlReviewQueue())
    ctx = _gate_ctx(tmp_path, pdf, [_candidate(quote)])
    # No phase1_fused + single processed page -> legacy single-page injection.
    block = asyncio.run(gate.run_evidence_gate(ctx))
    assert block["findings"]
    assert block["findings"][0]["source"]["page_num"] == 1
    assert block["stats"]["page_injected"] == 1  # legacy enrich semantics
    assert "marker_hint_hits" not in block["stats"]
