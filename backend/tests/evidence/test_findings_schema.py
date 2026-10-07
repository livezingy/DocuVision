"""G1 schema contract tests (P-029, design L1/L7).

Covers: literal enums, NOT_REPORTED conservation, silent-null rejection,
unreported-variant rejection, finding_id/sha12/quote_span shapes, ledger
integrity (reject requires ledger), prompt-version binding, JSONL envelope
roundtrip, slot-template registry, and the kie_configs pico template binding
(prompt_version + closed-list calibration against closed_lists.json).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, get_args

import pytest
import yaml

from app.services.evidence import findings_schema as fs

KIE_CONFIGS = (
    Path(__file__).resolve().parents[2] / "app" / "services" / "kie" / "kie_configs"
)


def valid_record_kwargs() -> Dict[str, Any]:
    return {
        "finding_id": "F-001",
        "source": {"paper_id": "pub_bmc", "page_num": 1, "sha12": "abe48cf91386", "doi": None},
        "quote": "Treatment may reduce infarct size.",
        "claim": "Treatment reduces infarct size.",
        "quote_span": [10, 38],
        "pico": {
            "population": "patients under cardiopulmonary bypass",
            "intervention": "phosphocreatine",
            "comparator": "placebo",
            "outcome": "infarct size",
            "follow_up": fs.NOT_REPORTED,
        },
        "claim_type": "original_finding",
        "verdict": "verbatim_exact",
        "hedge": {
            "source_hedge_terms": ["may"],
            "claim_hedge_terms": [],
            "fidelity": "overclaim",
        },
        "ledger": {"reject_class": "overclaim", "axis": "B", "excerpt": "quote hedge dropped"},
    }


def build_record() -> fs.FindingRecord:
    return fs.FindingRecord.model_validate(valid_record_kwargs())


def make_slot(**overrides: Any) -> Dict[str, str]:
    slots = {
        "population": "patients",
        "intervention": "drug X",
        "comparator": "placebo",
        "outcome": "mortality",
        "follow_up": fs.NOT_REPORTED,
    }
    slots.update(overrides)
    return {k: v for k, v in slots.items() if v is not None}


# --- enums (G1: 枚举 4+3+3) ---------------------------------------------------

def test_literal_enums_arity():
    assert get_args(fs.ClaimType) == (
        "original_finding", "background_citation", "speculation", "limitations")
    assert get_args(fs.Verdict) == ("verbatim_exact", "near_match", "unsupported")
    assert get_args(fs.FidelityKind) == ("faithful", "overclaim", "add_hedge")
    assert get_args(fs.RejectClass) == ("unsupported", "overclaim")
    assert get_args(fs.LedgerAxis) == ("A", "B")


# --- valid record + JSONL roundtrip ------------------------------------------

def test_valid_record_and_jsonl_roundtrip():
    record = build_record()
    line = fs.findings_jsonl_line(record)
    assert line["schema_version"] == fs.SCHEMA_VERSION
    assert line["prompt_version"] == fs.PROMPT_VERSION
    parsed = fs.parse_findings_jsonl_line(json.loads(json.dumps(line)))
    assert parsed == record


# --- NOT_REPORTED conservation + silent null (G1) -----------------------------

def test_not_reported_literal_accepted():
    kwargs = valid_record_kwargs()
    kwargs["pico"] = make_slot()
    assert fs.FindingRecord.model_validate(kwargs).pico.follow_up == fs.NOT_REPORTED


@pytest.mark.parametrize("bad_slot", [None, "", "   "])
def test_silent_null_slots_rejected(bad_slot):
    kwargs = valid_record_kwargs()
    if bad_slot is None:
        kwargs["pico"] = make_slot(outcome=None)
    else:
        kwargs["pico"] = make_slot(outcome=bad_slot)
    with pytest.raises(Exception):
        fs.FindingRecord.model_validate(kwargs)


def test_missing_slot_key_rejected():
    kwargs = valid_record_kwargs()
    kwargs["pico"] = make_slot()
    del kwargs["pico"]["comparator"]
    with pytest.raises(Exception):
        fs.FindingRecord.model_validate(kwargs)


@pytest.mark.parametrize("variant", ["not_reported", "not reported", "Not specified", "none"])
def test_unreported_variants_rejected(variant):
    kwargs = valid_record_kwargs()
    kwargs["pico"] = make_slot(outcome=variant)
    with pytest.raises(Exception):
        fs.FindingRecord.model_validate(kwargs)


# --- field shapes --------------------------------------------------------------

@pytest.mark.parametrize("fid", ["F-001", "F-045"])
def test_finding_id_accepted(fid):
    kwargs = valid_record_kwargs()
    kwargs["finding_id"] = fid
    assert fs.FindingRecord.model_validate(kwargs).finding_id == fid


@pytest.mark.parametrize("fid", ["F-1", "F-0001", "f-001", "F-12a", "F-"])
def test_finding_id_rejected(fid):
    kwargs = valid_record_kwargs()
    kwargs["finding_id"] = fid
    with pytest.raises(Exception):
        fs.FindingRecord.model_validate(kwargs)


def test_sha12_shape():
    kwargs = valid_record_kwargs()
    kwargs["source"]["sha12"] = None
    assert fs.FindingRecord.model_validate(kwargs).source.sha12 is None
    for bad in ("ABE48CF91386", "abe48cf9138", "abe48cf913868", "zzzzzzzzzzzz"):
        kwargs["source"]["sha12"] = bad
        with pytest.raises(Exception):
            fs.FindingRecord.model_validate(kwargs)


@pytest.mark.parametrize("span", [[0, 0], [10, 38]])
def test_quote_span_accepted(span):
    kwargs = valid_record_kwargs()
    kwargs["quote_span"] = span
    assert list(fs.FindingRecord.model_validate(kwargs).quote_span) == span


@pytest.mark.parametrize("span", [[38, 10], [-1, 5], [1], [1, 2, 3], [5, 5, 5]])
def test_quote_span_rejected(span):
    kwargs = valid_record_kwargs()
    kwargs["quote_span"] = span
    with pytest.raises(Exception):
        fs.FindingRecord.model_validate(kwargs)


# --- ledger integrity (G1/G3: reject 必填) ---------------------------------------

def test_unsupported_requires_ledger():
    kwargs = valid_record_kwargs()
    kwargs["verdict"] = "unsupported"
    kwargs["hedge"] = {"source_hedge_terms": [], "claim_hedge_terms": [], "fidelity": "faithful"}
    kwargs["ledger"] = None
    with pytest.raises(Exception):
        fs.FindingRecord.model_validate(kwargs)


def test_overclaim_requires_ledger():
    kwargs = valid_record_kwargs()
    kwargs["verdict"] = "near_match"
    kwargs["ledger"] = None
    with pytest.raises(Exception):
        fs.FindingRecord.model_validate(kwargs)


def test_ledger_class_mismatch_rejected():
    kwargs = valid_record_kwargs()
    kwargs["verdict"] = "unsupported"
    kwargs["hedge"] = {"source_hedge_terms": [], "claim_hedge_terms": [], "fidelity": "faithful"}
    kwargs["ledger"] = {"reject_class": "overclaim", "axis": "A", "excerpt": "paraphrase"}
    with pytest.raises(Exception):
        fs.FindingRecord.model_validate(kwargs)


def test_ledger_on_admitted_finding_rejected():
    kwargs = valid_record_kwargs()
    kwargs["hedge"] = {"source_hedge_terms": ["may"], "claim_hedge_terms": ["may"],
                       "fidelity": "faithful"}
    kwargs["ledger"] = {"reject_class": "unsupported", "axis": "A", "excerpt": "x"}
    with pytest.raises(Exception):
        fs.FindingRecord.model_validate(kwargs)


# --- version binding (G1) --------------------------------------------------------

def test_prompt_version_binding():
    # P-032 C4: pico template and contract both moved to v4.
    fs.check_prompt_version_binding("v4")
    for bad in ("v2", "V4", None, "v3"):
        with pytest.raises(fs.EvidenceSchemaError):
            fs.check_prompt_version_binding(bad)


def test_jsonl_envelope_version_binding():
    record = build_record()
    line = fs.findings_jsonl_line(record)
    bad_schema = dict(line, schema_version="evidence-findings/0.9")
    with pytest.raises(fs.EvidenceSchemaError):
        fs.parse_findings_jsonl_line(bad_schema)
    bad_prompt = dict(line, prompt_version="v2")
    with pytest.raises(fs.EvidenceSchemaError):
        fs.parse_findings_jsonl_line(bad_prompt)


# --- slot template registry -------------------------------------------------------

def test_slot_template_registry():
    assert fs.get_slot_template("pico") is fs.PicoSlots
    with pytest.raises(fs.EvidenceSchemaError):
        fs.get_slot_template("legal")
    with pytest.raises(fs.EvidenceSchemaError):
        fs.register_slot_template("pico", fs.PicoSlots)

    class LegalSlots(fs.PicoSlots):
        pass

    fs.register_slot_template("legal_test", LegalSlots)
    try:
        assert fs.get_slot_template("legal_test") is LegalSlots
    finally:
        fs.SLOT_TEMPLATES.pop("legal_test", None)


# --- kie_configs pico template binding + closed-list calibration -------------------

def test_pico_template_registered_and_version_bound():
    registry = yaml.safe_load((KIE_CONFIGS / "_registry.yaml").read_text(encoding="utf-8"))
    assert registry["types"]["pico"] == "pico"
    template = yaml.safe_load((KIE_CONFIGS / "pico.yaml").read_text(encoding="utf-8"))
    assert template["type_id"] == "pico"
    fs.check_prompt_version_binding(template.get("prompt_version"))
    schema = template["schema"]["findings"]
    for key in ("statement", "statement_type", "quote", "quote_block",
                "population", "intervention", "comparator", "outcome", "followup",
                "uncertainty"):
        assert key in schema


def test_pico_prompt_carries_exactly_the_closed_hedge_list():
    closed = json.loads(
        (Path(fs.__file__).parent / "closed_lists.json").read_text(encoding="utf-8"))
    assert closed["schema_version"] == "closed_lists/1.0"
    hedge_en = closed["hedge"]["en"]
    assert len(hedge_en) == 14
    template = yaml.safe_load((KIE_CONFIGS / "pico.yaml").read_text(encoding="utf-8"))
    prompt = template["prompt_template"]
    marker = "closed list of hedging words:"
    assert marker in prompt
    listed = prompt.split(marker, 1)[1].split(". Copy verbatim", 1)[0]
    listed_words = [w.strip() for w in listed.replace("hedging words:", "").split(",")]
    assert listed_words == hedge_en


def test_pico_template_header_bound_to_contract():
    # P-032 C4 (adjudication 1): pico.yaml's prompt_version header and the
    # contract PROMPT_VERSION must be the same value -- checked against the
    # real config file, not a literal, so either side drifting fails here.
    from pathlib import Path

    import yaml

    config = (
        Path(__file__).resolve().parents[2]
        / "app" / "services" / "kie" / "kie_configs" / "pico.yaml"
    )
    header = yaml.safe_load(config.read_text(encoding="utf-8"))["prompt_version"]
    fs.check_prompt_version_binding(header)
