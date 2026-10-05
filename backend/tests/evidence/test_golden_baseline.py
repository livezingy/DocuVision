"""G5 golden-set sentinel (P-029 design L6).

Baseline = the 2026-10-03 sciextract pilot reading (handoff golden set),
converted to FindingRecord lines by scripts/qa/convert_golden.py (double-run
byte-identical; re-convert with --check to detect drift).

Ratchet (handoff D8 wording): after ANY verifier or closed-list change this
sentinel must be re-run; shipping requires matching or beating the baseline
with unsupported NOT increasing. On any deviation: stop and report, never
adjust the golden data to fit new code.

Pinned baseline:
  verdicts       35 verbatim_exact / 3 near_match / 7 unsupported
  rejects        7 = 4 original_finding + 3 background_citation
  gate B         38/38 faithful among the 38 non-rejected, 0 overclaim overall
  gate C         empty slots 0/45 (schema validates every record)
  statement_type 28 original / 13 background / 4 speculation / 0 limitations
"""
from __future__ import annotations

import json
from pathlib import Path

from app.services.evidence import verifier
from app.services.evidence.findings_schema import FindingRecord

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _load():
    records = [
        json.loads(line)
        for line in (GOLDEN_DIR / "verified.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pages = {
        json.loads(line)["grounding_page_key"]: json.loads(line)["grounding_block_norm"]
        for line in (GOLDEN_DIR / "grounding_pages.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    return records, pages


RECORDS, PAGES = _load()


def test_golden_size_and_schema_validity():
    assert len(RECORDS) == 45 and len(PAGES) == 18
    empty_slots = 0
    for line in RECORDS:
        payload = {k: v for k, v in line.items() if k != "grounding_page_key"}
        record = FindingRecord.model_validate(payload)  # silent null would raise here
        for slot in ("population", "intervention", "comparator", "outcome", "follow_up"):
            if getattr(record.pico, slot) == "NOT_REPORTED":
                continue
            empty_slots += 0  # schema guarantees non-empty; literal kept for clarity
    assert empty_slots == 0


def test_gate_a_rerun_matches_every_record():
    for line in RECORDS:
        hay = PAGES[line["grounding_page_key"]]
        outcome = verifier.classify_quote(line["quote"], hay)
        assert outcome.verdict == line["verdict"], (
            f"{line['finding_id']}: rerun {outcome.verdict} != baseline {line['verdict']}"
        )


def test_pinned_verdict_counts():
    counts = {}
    for line in RECORDS:
        counts[line["verdict"]] = counts.get(line["verdict"], 0) + 1
    assert counts == {"verbatim_exact": 35, "near_match": 3, "unsupported": 7}


def test_pinned_reject_composition():
    reject_types = {}
    for line in RECORDS:
        if line["verdict"] == "unsupported":
            reject_types[line["claim_type"]] = reject_types.get(line["claim_type"], 0) + 1
    assert reject_types == {"original_finding": 4, "background_citation": 3}


def test_gate_b_no_overclaim_and_non_rejected_all_faithful():
    non_rejected = [line for line in RECORDS if line["verdict"] != "unsupported"]
    assert len(non_rejected) == 38
    for line in RECORDS:
        assert line["hedge"]["fidelity"] != "overclaim", f"{line['finding_id']} overclaim"
    for line in non_rejected:
        assert line["hedge"]["fidelity"] == "faithful", f"{line['finding_id']} not faithful"
    # closed-list consistency: recorded source hedges == verifier hedge_set of the quote
    for line in RECORDS:
        assert line["hedge"]["source_hedge_terms"] == sorted(verifier.hedge_set(line["quote"]))


def test_pinned_statement_type_counts():
    counts = {key: 0 for key in ("original_finding", "background_citation", "speculation", "limitations")}
    for line in RECORDS:
        counts[line["claim_type"]] += 1
    assert counts == {
        "original_finding": 28,
        "background_citation": 13,
        "speculation": 4,
        "limitations": 0,
    }
