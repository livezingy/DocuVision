"""G3 gate tests (P-029, design L4/L5).

Covers: overclaim hard-reject (ledger axis B + export blocked), add_hedge
counted-only, near_match HITL routing, ledger presence on rejected records,
fail-closed grounding rules (missing/untrusted page -> unsupported), slot
incompleteness and schema-invalid candidates routed to human review, slot
canonicalization, findings JSONL envelope validity, the default-off flag,
and the orchestrator hook's zero-behavior guarantee when disabled.
"""
from __future__ import annotations

import asyncio

import fitz
import pytest

from app.services.evidence import gate
from app.services.evidence.findings_schema import (
    NOT_REPORTED,
    parse_findings_jsonl_line,
)
from app.services.hitl_queue import HitlReviewQueue

QUOTE = "Treatment may reduce infarct size in patients."
CLAIM = "Treatment reduces infarct size in patients."


def grounded_candidate(**overrides):
    candidate = {
        "statement": CLAIM,
        "statement_type": "original_finding",
        "quote": QUOTE,
        "page": 1,
        "population": "patients under cardiopulmonary bypass",
        "intervention": "phosphocreatine",
        "comparator": "placebo",
        "outcome": "infarct size",
        "followup": "not reported",
    }
    candidate.update(overrides)
    return candidate


PAGES = {1: QUOTE + " Follow-up was 30 days."}
TRUSTED = {1}


def test_overclaim_hard_reject_blocks_export():
    report = gate.verify_candidates([grounded_candidate()], PAGES, TRUSTED, "doc.pdf")
    assert report.rejected == 1
    assert report.export_allowed is False
    ledger = report.ledger[0]
    assert ledger["reject_class"] == "overclaim" and ledger["axis"] == "B"
    record = report.records[0]
    assert record.ledger is not None and record.ledger.reject_class == "overclaim"


def test_add_hedge_counted_only_not_rejected():
    candidate = grounded_candidate(quote=QUOTE, statement="Treatment may possibly reduce infarct size.")
    report = gate.verify_candidates([candidate], PAGES, TRUSTED, "doc.pdf")
    assert report.rejected == 0 and report.export_allowed is True
    assert report.records[0].hedge.fidelity == "add_hedge"


def test_near_match_routed_to_hitl_and_exported():
    quote = " ".join(["word"] * 27) + " a b c"
    hay = " ".join(["word"] * 27) + " other ending words"
    candidate = grounded_candidate(quote=quote)
    candidate["statement"] = quote
    report = gate.verify_candidates([candidate], {1: hay}, TRUSTED, "doc.pdf")
    assert report.near_match == 1
    assert report.export_allowed is True
    reason, payload = report.hitl_payloads[0]
    assert reason == gate.EVIDENCE_HITL_NEAR_MATCH
    assert payload["evidence_schema_version"]
    assert payload["closed_lists_version"] and payload["hedge_en"]


def test_rejected_records_carry_valid_ledger_lines():
    report = gate.verify_candidates(
        [
            grounded_candidate(),  # overclaim
            grounded_candidate(quote="Entirely unrelated sentence here.", statement=CLAIM),  # unsupported
        ],
        PAGES,
        TRUSTED,
        "doc.pdf",
    )
    assert report.rejected == 2 and report.export_allowed is False
    for line in report.lines:
        record = parse_findings_jsonl_line(line)
        if record.verdict == "unsupported" or record.hedge.fidelity == "overclaim":
            assert record.ledger is not None
    classes = {entry["reject_class"] for entry in report.ledger}
    assert classes == {"overclaim", "unsupported"}


@pytest.mark.parametrize("pages,trusted", [({}, set()), ({2: QUOTE}, {2}), ({1: QUOTE}, set())])
def test_missing_or_untrusted_grounding_is_fail_closed(pages, trusted):
    report = gate.verify_candidates([grounded_candidate()], pages, trusted, "doc.pdf")
    assert report.rejected == 1
    record = report.records[0]
    assert record.verdict == "unsupported"
    assert record.quote_span is None


def test_incomplete_slots_routed_to_hitl_not_exported():
    candidate = grounded_candidate(population="   ", comparator=None)
    report = gate.verify_candidates([candidate], PAGES, TRUSTED, "doc.pdf")
    assert report.exported == 0 and report.export_allowed is True
    reason, payload = report.hitl_payloads[0]
    assert reason == gate.EVIDENCE_HITL_SLOT
    assert "population" in payload["detail"]


def test_schema_invalid_routed_to_hitl_not_exported():
    candidate = grounded_candidate(statement_type="not_a_type")
    report = gate.verify_candidates([candidate], PAGES, TRUSTED, "doc.pdf")
    assert report.exported == 0
    assert report.hitl_payloads[0][0] == gate.EVIDENCE_HITL_SCHEMA


def test_unreported_variants_canonicalized():
    slots = gate.canonicalize_slots(
        {"population": "not reported", "intervention": "not_reported",
         "comparator": "Not specified", "outcome": "none", "followup": "2 years"}
    )
    assert slots["population"] == NOT_REPORTED and slots["intervention"] == NOT_REPORTED
    assert slots["comparator"] == NOT_REPORTED and slots["outcome"] == NOT_REPORTED
    assert slots["follow_up"] == "2 years"


def test_page_sha12_is_stable_hex():
    assert gate.page_sha12("abc") == gate.page_sha12("abc")
    assert len(gate.page_sha12("abc")) == 12


# --- pipeline hook (flag off = zero behavior; on = end-to-end routing) --------


class _StubOrchestrator:
    """Minimal step-collaborator stub (ensure_not_cancelled + progress)."""

    def ensure_not_cancelled(self, ctx):
        return None

    async def update_progress(self, ctx, progress, message):
        return None


def _make_pdf(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), QUOTE + " Follow-up was 30 days.")
    pdf_path = tmp_path / "doc.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_evidence_step_disabled_is_zero_behavior(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.orchestration.document_pipeline_orchestrator import evidence_step

    monkeypatch.setattr(settings, "EVIDENCE_ENABLED", False)
    ctx = {"task_id": "t", "task": {"file_name": "doc.pdf"}, "file_path": _make_pdf(tmp_path),
           "result": {"kie_fields": {"findings": [grounded_candidate()]}},
           "orchestrator": _StubOrchestrator()}
    asyncio.run(evidence_step(ctx))
    assert "evidence" not in ctx["result"]


def test_run_evidence_gate_end_to_end(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.orchestration.document_pipeline_orchestrator import evidence_step
    from app.services import hitl_queue as hq_module

    monkeypatch.setattr(settings, "EVIDENCE_ENABLED", True)
    fresh_queue = HitlReviewQueue()
    monkeypatch.setattr(hq_module, "hitl_queue", fresh_queue)

    pdf_path = _make_pdf(tmp_path)
    fused = {"pages": [{"page": 1, "blocks": [{"payload": {"text": QUOTE + " Follow-up was 30 days."}}]}]}
    ctx = {
        "task_id": "t-e2e",
        "task": {"file_name": "doc.pdf"},
        "file_path": pdf_path,
        "result": {"kie_fields": {"findings": [grounded_candidate()]}},
        "phase1_fused": fused,
        "orchestrator": _StubOrchestrator(),
    }
    asyncio.run(evidence_step(ctx))

    block = ctx["result"]["evidence"]
    assert block["export_allowed"] is False  # overclaim candidate rejected
    assert len(block["findings"]) == 1
    assert block["failure_ledger"][0]["reject_class"] == "overclaim"


def test_run_evidence_gate_no_findings_is_clean_noop(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.orchestration.document_pipeline_orchestrator import evidence_step

    monkeypatch.setattr(settings, "EVIDENCE_ENABLED", True)
    ctx = {"task_id": "t", "task": {"file_name": "doc.pdf"}, "file_path": str(tmp_path / "x.pdf"),
           "result": {"kie_fields": {}}, "orchestrator": _StubOrchestrator()}
    asyncio.run(evidence_step(ctx))
    block = ctx["result"]["evidence"]
    assert block["findings"] == [] and block["export_allowed"] is True


def test_evidence_flag_defaults_off():
    from app.core.config import Settings

    fresh = Settings()
    assert fresh.EVIDENCE_ENABLED is False
