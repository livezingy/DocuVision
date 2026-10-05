"""G2 verifier tests (P-029, design L2/L7).

Covers: one verbatim_exact case per ladder variant V0-V6, near_match prefix
boundaries (total-3 words / 0.90 ratio, both inclusive), the unsupported
falls, never-silently-corrected properties, fidelity (overclaim hard-reject /
add_hedge counted only), Gate C slot rows, reject precedence, GBK-safe
diagnostics, and the independence guard (no KIE imports).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services.evidence import verifier as v

# --- Gate A: one verbatim_exact case per ladder variant -----------------------

VARIANTS = [
    ("V0", "Patient outcomes improved.", "Patient outcomes improved."),
    ("V1", "cafe\u0301 trial", "caf\u00e9 trial done"),  # NFD quote -> NFC hit
    ("V2", "\ufb01x the kit", "fix the kit now"),  # ligature fi -> fi
    ("V3", "outcomes   improved.", "outcomes improved."),  # whitespace collapse
    ("V4", "IQR 6,838\u201319,034", "IQR 6,838-19,034 was stable"),  # en dash -> hyphen
    ("V5", "car- dioprotective", "the cardioprotective effect"),  # hyphen rejoin
    ("V6", "meta-analysis", "a metaanalysis of trials"),  # hyphen strip
]


@pytest.mark.parametrize("variant,quote,hay", VARIANTS)
def test_ladder_variant_hits_verbatim_exact(variant, quote, hay):
    got = v.classify_quote(quote, hay)
    assert got.verdict == v.VERBATIM_EXACT
    assert got.matched_variant == variant
    assert got.span is not None


def test_nfc_variant_v1_via_decomposed_quote():
    got = v.classify_quote("cafe\u0301 trial", "caf\u00e9 trial done")
    assert (got.verdict, got.matched_variant) == (v.VERBATIM_EXACT, "V1")


def test_span_offsets_inside_matched_variant():
    hay = "intro text. Patient outcomes improved. trailing"
    got = v.classify_quote("Patient outcomes improved.", hay)
    start, end = got.span
    assert hay[start:end] == "Patient outcomes improved."


# --- near_match prefix boundaries ----------------------------------------------

def _prefix_pair(total: int, pref: int):
    quote = " ".join(["word"] * pref) + " tail extras here"
    hay = " ".join(["word"] * pref) + " entirely different ending words"
    return quote, hay


def test_near_match_inclusive_boundaries():
    # pref = total - 3 and ratio = 0.90 exactly (both pins inclusive)
    quote, hay = _prefix_pair(30, 27)
    quote = " ".join(["word"] * 27) + " a b c"
    hay = " ".join(["word"] * 27) + " other ending words"
    got = v.classify_quote(quote, hay)
    assert got.verdict == v.NEAR_MATCH
    assert got.matched_variant is None and got.span is None
    assert got.detail == "27/30w prefix"


def test_total_minus_three_holds_but_ratio_fails():
    # total=10, pref=7: pref >= total-3 holds, ratio 0.7 < 0.90 -> unsupported
    quote = " ".join(["word"] * 7) + " a b c"
    hay = " ".join(["word"] * 7) + " entirely different ending"
    assert v.classify_quote(quote, hay).verdict == v.UNSUPPORTED


def test_ratio_holds_but_total_minus_three_fails():
    # total=40, pref=36: ratio = 0.90 holds, pref < total-3 = 37 -> unsupported
    quote = " ".join(["word"] * 36) + " a b c d"
    hay = " ".join(["word"] * 36) + " other words entirely different here"
    assert v.classify_quote(quote, hay).verdict == v.UNSUPPORTED


def test_below_both_bounds_unsupported():
    quote = " ".join(["word"] * 6) + " a b c d"
    hay = " ".join(["word"] * 6) + " other words entirely different here"
    assert v.classify_quote(quote, hay).verdict == v.UNSUPPORTED


# --- never silently corrected ---------------------------------------------------

def test_quote_never_corrected_on_miss():
    quote = "The treament reduces risk."  # typo on purpose, absent from haystack
    hay = "The treatment reduces risk in this trial cohort."
    got = v.classify_quote(quote, hay)
    assert got.verdict == v.UNSUPPORTED
    assert got.span is None
    assert quote == "The treament reduces risk."  # input untouched
    again = v.classify_quote(quote, hay)
    assert (again.verdict, again.detail, again.span) == (got.verdict, got.detail, got.span)


def test_diagnostics_are_ascii():
    got = v.classify_quote("可能有效果的结果", "完全无关的文本内容")
    assert got.verdict == v.UNSUPPORTED
    assert got.detail.isascii()


# --- Gate B: fidelity ------------------------------------------------------------

SLOTS_OK = {"population": "p", "intervention": "i", "comparator": "c",
            "outcome": "o", "follow_up": "f"}


def test_overclaim_hard_reject():
    got = v.audit_finding("may reduce risk", "reduces risk clearly", SLOTS_OK, "hay text")
    assert got.fidelity == v.OVERCLAIM
    assert got.rejected and got.reject_class == v.OVERCLAIM


def test_faithful_keeps_source_hedge():
    got = v.audit_finding("may reduce risk", "may reduce risk", SLOTS_OK,
                          "may reduce risk in this cohort")
    assert got.fidelity == v.FAITHFUL
    assert got.source_hedge_terms == ["may"] and got.claim_hedge_terms == ["may"]
    assert not got.rejected


def test_add_hedge_counted_not_rejected():
    got = v.audit_finding("reduces risk clearly", "may reduce risk", SLOTS_OK,
                          "reduces risk clearly in this cohort")
    assert got.fidelity == v.ADD_HEDGE
    assert got.claim_hedge_terms == ["may"]
    assert not got.rejected  # add_hedge only counted, never rejected (design L2)


# --- Gate C: slot completeness ----------------------------------------------------

@pytest.mark.parametrize("bad", [{}, {"population": "", "intervention": "i",
                                      "comparator": "c", "outcome": "o", "follow_up": None}])
def test_incomplete_slots_flagged(bad):
    rows = v.check_slots(bad)
    assert rows, "empty/missing slots must produce Gate C rows"


def test_not_reported_slots_pass_gate_c():
    slots = dict(SLOTS_OK, follow_up="NOT_REPORTED")
    assert v.check_slots(slots) == []


# --- reject precedence --------------------------------------------------------------

def test_overclaim_wins_over_unsupported():
    got = v.audit_finding("may reduce risk", "reduces risk", SLOTS_OK, "unrelated haystack")
    assert got.verdict == v.UNSUPPORTED and got.fidelity == v.OVERCLAIM
    assert got.reject_class == v.OVERCLAIM


def test_near_match_faithful_not_rejected():
    quote = " ".join(["word"] * 27) + " a b c"
    hay = " ".join(["word"] * 27) + " other ending words"
    got = v.audit_finding(quote, quote, SLOTS_OK, hay)
    assert got.verdict == v.NEAR_MATCH and not got.rejected


# --- independence guard (design L2: zero KIE imports) --------------------------------

def test_verifier_imports_no_kie_modules():
    source = Path(v.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert "kie" not in name.lower(), f"verifier must not import KIE code: {name}"
