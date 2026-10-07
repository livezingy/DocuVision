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
from app.services.kie import text_first as tf
from app.services.kie.KieManager import KieManager
from app.services.kie_qwen_service import QwenDocumentKIEService, _merge_text_window_fields

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
            "kie_meta": {"kie_pages_processed": [1], "resolved_document_type": "pico"},
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


def test_d2_gate_text_first_scope_mirrors_m1(tmp_path, monkeypatch):
    """D2: the gate must follow the SAME decision as the KIE extraction step.

    Flag on but a resolved doc type M1 would NOT run text-first for (non-pico):
    the gate must take the legacy enrich path too, so the extraction channel and
    the grounding path cannot diverge."""
    quote = "Treatment may reduce infarct size in patients."
    pdf = _make_pdf(tmp_path, pages=((("Before it. " + quote + " After it.",), ()),))
    monkeypatch.setattr(settings, "EVIDENCE_ENABLED", True)
    monkeypatch.setattr(settings, "EVIDENCE_TEXT_FIRST", True)
    import app.services.hitl_queue as hq_module

    monkeypatch.setattr(hq_module, "hitl_queue", HitlReviewQueue())
    assert tf.text_first_enabled("invoice", is_pdf=True) is False  # M1 side
    ctx = _gate_ctx(tmp_path, pdf, [_candidate(quote)])
    ctx["result"]["kie_meta"]["resolved_document_type"] = "invoice"
    block = asyncio.run(gate.run_evidence_gate(ctx))
    assert "marker_hint_hits" not in block["stats"]  # legacy path, same as M1
    assert block["stats"]["page_injected"] == 1


def test_d2_gate_text_first_requires_pdf(tmp_path, monkeypatch):
    """Non-PDF input: M1 stays on the image channel, so the gate must too."""
    quote = "Treatment may reduce infarct size in patients."
    monkeypatch.setattr(settings, "EVIDENCE_ENABLED", True)
    monkeypatch.setattr(settings, "EVIDENCE_TEXT_FIRST", True)
    import app.services.hitl_queue as hq_module

    monkeypatch.setattr(hq_module, "hitl_queue", HitlReviewQueue())
    ctx = _gate_ctx(tmp_path, tmp_path / "note.txt", [_candidate(quote)])
    block = asyncio.run(gate.run_evidence_gate(ctx))
    assert "marker_hint_hits" not in block["stats"]  # legacy path
    assert block["stats"]["page_injected"] == 1


# ------------------------------------------------- M1: marker / window / payload


def test_m1_block_marker_and_payload():
    assert tf.block_marker(5, 0) == "[p5_b0]"
    payload = tf.build_page_payload(["alpha", "beta"], 5)
    assert payload == "[p5_b0] alpha\n[p5_b1] beta"


def test_m1_split_windows_single_window_and_overlap(monkeypatch):
    blocks = ["short one", "short two", "short three"]
    windows = tf.split_windows(blocks, 7)
    assert windows == ["[p7_b0] short one\n[p7_b1] short two\n[p7_b2] short three"]

    monkeypatch.setattr(tf, "TEXT_FIRST_WINDOW_MAX_CHARS", 60)
    big = ["a" * 20, "b" * 20, "c" * 20, "d" * 20]
    windows = tf.split_windows(big, 2)
    # 1-block overlap: each window after the first re-opens with the previous
    # window's last block, and every marker keeps the absolute page number.
    assert len(windows) == 3
    assert windows[1].startswith("[p2_b1] ")
    assert windows[2].startswith("[p2_b2] ")
    for window in windows:
        assert len(window) <= 60


def test_m1_split_windows_oversize_single_block(monkeypatch):
    monkeypatch.setattr(tf, "TEXT_FIRST_WINDOW_MAX_CHARS", 10)
    windows = tf.split_windows(["x" * 50, "y3"], 1)
    assert len(windows) == 2
    assert windows[0] == "[p1_b0] " + "x" * 50  # a block is never split further
    assert windows[1] == "[p1_b1] y3"


def _layout(elements):
    return {"elements": elements}


def _elem(page, type_, text):
    return {"page": page, "type": type_, "text": text}


def test_m2_select_body_pages_boundaries():
    cover = [_elem(1, "title", "Cover Page Title Here")]
    body = [_elem(2, "text", "x" * 100) for _ in range(5)]  # 5 elems / 500 chars
    # exact boundary: 8 elements of body types and 500 chars -> included
    exact = cover + body + [_elem(2, "table", "y") for _ in range(3)]
    pages = tf.select_body_pages(_layout(exact), page_count=3)
    assert pages == [2]
    # below either bound -> excluded
    under_elems = cover + body[:4] + [_elem(2, "table", "y") for _ in range(3)]
    assert tf.select_body_pages(_layout(under_elems), page_count=3) == []
    under_chars = cover + [_elem(2, "text", "x" * 62) for _ in range(8)]
    assert tf.select_body_pages(_layout(under_chars), page_count=3) == []
    # non-body types do not count
    figures = cover + [_elem(2, "figure", "z" * 100) for _ in range(9)]
    assert tf.select_body_pages(_layout(figures), page_count=3) == []


def test_m2_resolve_pages_text_first(monkeypatch):
    layout = _layout([_elem(2, "text", "x" * 100) for _ in range(9)])
    # flag off -> legacy parse verbatim
    assert tf.resolve_pages_text_first(None, 3, 5, text_first=False) == ([1], False)
    assert tf.resolve_pages_text_first("2-3", 3, 5, text_first=False) == ([2, 3], False)
    # flag on + default spec -> body pages (M2 adjudication), then truncation
    assert tf.resolve_pages_text_first(None, 3, 5, text_first=True, layout=layout) == ([2], False)
    assert tf.resolve_pages_text_first("1", 3, 5, text_first=True, layout=layout) == ([2], False)
    # explicit spec under flag on -> honoured as-is
    assert tf.resolve_pages_text_first("1,3", 3, 5, text_first=True, layout=layout) == ([1, 3], False)
    # no body pages found -> safe fallback to page 1
    assert tf.resolve_pages_text_first(None, 3, 5, text_first=True, layout={"elements": []}) == ([1], False)
    # truncation flag
    many = _layout([_elem(p, "text", "x" * 100) for p in (1, 2, 3) for _ in range(9)])
    pages, truncated = tf.resolve_pages_text_first(None, 3, 2, text_first=True, layout=many)
    assert pages == [1, 2] and truncated is True


def test_m2_text_first_enabled_flag(monkeypatch):
    monkeypatch.setattr(settings, "EVIDENCE_TEXT_FIRST", True)
    assert tf.text_first_enabled("pico", is_pdf=True) is True
    assert tf.text_first_enabled("invoice", is_pdf=True) is False
    assert tf.text_first_enabled("pico", is_pdf=False) is False
    monkeypatch.setattr(settings, "EVIDENCE_TEXT_FIRST", False)
    assert tf.text_first_enabled("pico", is_pdf=True) is False


def test_m1_build_text_first_payloads_sources(tmp_path):
    pdf = _make_pdf(
        tmp_path,
        name="mixed.pdf",
        pages=(
            (("born digital body text for page one",), ()),
            ((), ("ghost text",)),  # invisible-only page: M5 predicate fails
            ((), ()),
        ),
    )
    layout = _layout([_elem(2, "text", "ocr text for page two")])
    payloads = tf.build_text_first_payloads(pdf, layout, [1, 2, 3])
    assert payloads[1]["source"] == tf.SOURCE_TEXT_LAYER
    assert "[p1_b0]" in payloads[1]["windows"][0]
    assert payloads[2]["source"] == tf.SOURCE_FUSED_OCR  # declared fallback (R3)
    assert "[p2_b0] ocr text for page two" in payloads[2]["windows"]
    assert 3 not in payloads  # no text anywhere -> image channel (visible by absence)
    assert payloads[1]["n_chars"] > 0


def test_m1_kie_manager_text_branch_sends_no_image(monkeypatch):
    mgr = KieManager(model=object(), processor=object())
    captured = {}

    def fake_generate(messages, max_new_tokens=2048):
        captured["messages"] = messages
        return '{"findings": [{"quote": "q", "statement": "s"}]}'

    monkeypatch.setattr(mgr, "_qwen_generate", fake_generate)
    result = mgr.extract_text_first("[p1_b0] body text", "pico")
    assert result["type"] == "pico"
    assert result["fields"]["findings"][0]["quote"] == "q"
    content = captured["messages"][0]["content"]
    assert not any(item.get("type") == "image" for item in content)
    assert "[p1_b0] body text" in content[0]["text"]


def test_m1_merge_text_window_fields_dedupes_overlap():
    merged = _merge_text_window_fields(
        [
            {"findings": [{"quote": "q1", "statement": "s1"}, {"quote": "q2", "statement": "s2"}]},
            {"findings": [{"quote": "q2", "statement": "s2"}, {"quote": "q3", "statement": "s3"}]},
        ]
    )
    assert [f["quote"] for f in merged["findings"]] == ["q1", "q2", "q3"]
    merged2 = _merge_text_window_fields([{"raw_output": "noise"}, {"raw_output": "other", "note": "kept"}])
    assert merged2["raw_output"] == "noise" and merged2["note"] == "kept"


def test_m1_service_text_first_channel(monkeypatch):
    svc = QwenDocumentKIEService()

    class FakeMgr:
        def extract_text_first(self, text, document_type, query_fields=None, merged_schema=None):
            assert not query_fields and not merged_schema
            return {"type": document_type, "fields": {"findings": [{"quote": "q1", "statement": "s1"}]}}

    monkeypatch.setattr(svc, "_manager", FakeMgr())
    payload = {
        "page": 1,
        "source": tf.SOURCE_TEXT_LAYER,
        "n_chars": 42,
        "windows": ["window one [p1_b0] a", "window two [p1_b1] b"],
    }
    result = asyncio.run(svc.extract_fields("paper.pdf", "pico", text_payload=payload))
    assert result["fields"]["findings"] == [{"quote": "q1", "statement": "s1"}]  # overlap dedupe
    debug = result["debug_input"]
    assert debug["mode"] == "text_first" and debug["input_source"] == "text_layer"
    assert debug["n_windows"] == 2 and debug["window_chars"] == [len(payload["windows"][0]), len(payload["windows"][1])]
    assert result["metadata"]["text_first"] == {"source": "text_layer", "n_windows": 2}
    assert result["confidence_avg"] >= 0.0


# ------------------------------------- C1a: real-corpus life gate (local face)


def test_c1a_bmc_page5_text_first_grounding_hit(tmp_path, monkeypatch):
    """C1 life anchor, local face (P-032 §2 C1): on the real pub_bmc paper,
    a verbatim page-5 quote from the M1 payload grounds deterministically to
    (page=5, span non-empty), and the M5 predicate trusts page 1."""
    import app.services.hitl_queue as hq_module

    source = grounding_source(str(BMC_PDF))
    blocks5 = source.blocks[5]
    assert blocks5, "page 5 must carry native text blocks"
    block_idx = next(
        i for i, text in enumerate(blocks5) if "no differences in peak troponin" in text
    )
    # The model's quote is copied verbatim from the payload block text (C1:
    # quote exists verbatim in the grounding text by construction).
    quote = "There were no differences in peak troponin"
    assert quote in blocks5[block_idx]

    monkeypatch.setattr(settings, "EVIDENCE_ENABLED", True)
    monkeypatch.setattr(settings, "EVIDENCE_TEXT_FIRST", True)
    monkeypatch.setattr(hq_module, "hitl_queue", HitlReviewQueue())
    ctx = _gate_ctx(tmp_path, BMC_PDF, [_candidate(quote, quote_block=f"[p5_b{block_idx}]")])
    block = asyncio.run(gate.run_evidence_gate(ctx))
    assert block["findings"], block
    record = block["findings"][0]
    assert record["source"]["page_num"] == 5  # 接地命中：page=5
    assert record["verdict"] == "verbatim_exact"
    assert record["quote_span"]  # span 非空
    assert block["export_allowed"] is True
    assert block["stats"]["page_injected"] == 1
    assert block["stats"]["marker_hint_hits"] == 1  # marker hint resolved it
    # M5 predicate: BMC page 1 (invisible_ratio 0.0, image_coverage ~0.61)
    # is trusted under the evidence criterion -- the C1 DoD pair.
    assert 1 in block["stats"]["trusted_pages"]
    assert 5 in block["stats"]["trusted_pages"]


def test_c1a_bmc_payload_covers_page5():
    """M2 DoD local face: the payload builder on the real corpus covers page 5
    (the findings page) with text_layer source and absolute-page markers."""
    payloads = tf.build_text_first_payloads(str(BMC_PDF), {"elements": []}, list(range(1, 6)))
    assert 5 in payloads and payloads[5]["source"] == tf.SOURCE_TEXT_LAYER
    assert any("[p5_b" in window for window in payloads[5]["windows"])
