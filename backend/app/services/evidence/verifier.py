"""Evidence verifier: Gate A quote grounding + Gate B hedge fidelity + Gate C slots.

Ported from the sciextract handover asset ``verify_quotes.py`` (sha256[:12]
047298c64f75) per design L2/D3, with the handover's normalization ladder
formalized as the fixed V0-V6 variant ladder (design L2, order is pinned):

    V0 raw
    V1 NFC
    V2 V1 + ligature expansion
    V3 V2 + whitespace collapse
    V4 V3 + soft-hyphen strip + dash/quote punctuation normalization
    V5 V4 + hyphen rejoin (line-break hyphens already collapsed to "hyphen space")
    V6 V5 + hyphen strip

Classification (pinned, design L2): a hit at any ladder variant is
``verbatim_exact`` (the matched variant is recorded); otherwise a word-prefix
match on the handover criterion (``pref >= total - 3`` and ``pref/total >=
0.90``, prefix of the V4 quote against the V6 haystack) is ``near_match``;
everything else is ``unsupported``. Gate B compares hedge words from the
closed list: a hedge present in the quote but dropped from the claim is
``overclaim`` (hard reject); a hedge added by the claim is ``add_hedge``
(counted, never rejected). Gate C flags incomplete PICO slots.

Discipline: never silently corrected -- the quote text is never rewritten and
verdicts are never repaired; this module imports no KIE extraction code and
shares no matching logic with it. All file I/O is UTF-8 and all diagnostics
are ASCII (Windows GBK guard).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.services.evidence.normalize import LIGATURES

VERBATIM_EXACT = "verbatim_exact"
NEAR_MATCH = "near_match"
UNSUPPORTED = "unsupported"
FAITHFUL = "faithful"
OVERCLAIM = "overclaim"
ADD_HEDGE = "add_hedge"

NEAR_MIN_RATIO = 0.90
NEAR_MAX_MISSING_WORDS = 3

_LADDER_NAMES = ("V0", "V1", "V2", "V3", "V4", "V5", "V6")

_HEDGE_REJOIN = re.compile(r"(?<=[a-z])- (?=[a-z])")
_CLOSED_LISTS_PATH = Path(__file__).resolve().parent / "closed_lists.json"

# Closed-list hedge words (single source: closed_lists.json, design L3). The
# ZH list is empty until the first Chinese-domain data PR; CJK matching will
# need non-\b tokenization when it is seeded, so hedge_set() must be revisited
# together with that data change.
with _CLOSED_LISTS_PATH.open("r", encoding="utf-8") as _fh:
    _CLOSED = json.load(_fh)
HEDGE_WORDS: tuple = tuple(_CLOSED["hedge"]["en"]) + tuple(_CLOSED["hedge"]["zh"])


def hedge_set(text: str) -> set:
    """Hedge words from the closed list present in ``text`` (whole words, case-insensitive)."""
    return {h for h in HEDGE_WORDS if re.search(r"\b" + re.escape(h) + r"\b", text, re.I)}


def _ladder_variants(text: str) -> list:
    """Return the seven ladder variants of ``text``, in pinned order V0..V6."""
    v0 = text
    v1 = unicodedata.normalize("NFC", v0)
    v2 = v1
    for k, v in LIGATURES.items():
        v2 = v2.replace(k, v)
    v3 = " ".join(v2.split())
    v4 = (v3.replace("\u2018", "'").replace("\u2019", "'")
          .replace("\u201c", '"').replace("\u201d", '"')
          .replace("\u2013", "-").replace("\u2014", "-")
          .replace("\u2212", "-").replace("\u00a0", " ")
          .replace("\u00ad", ""))
    v5 = _HEDGE_REJOIN.sub("", v4)
    v6 = v5.replace("-", "")
    return [v0, v1, v2, v3, v4, v5, v6]


def longest_prefix_words(quote_v3: str, haystack_v6: str) -> int:
    """Longest word prefix of the quote contained in the haystack (binary search)."""
    words = quote_v3.split()
    lo, hi = 0, len(words)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if " ".join(words[:mid]) in haystack_v6:
            lo = mid
        else:
            hi = mid - 1
    return lo


@dataclass
class QuoteMatch:
    """Gate A outcome for one quote against one grounding text."""

    verdict: str
    matched_variant: Optional[str] = None
    detail: str = ""
    span: Optional[tuple] = None  # [start, end] inside the matched variant of the haystack


def classify_quote(quote: str, haystack: str) -> QuoteMatch:
    """Gate A: ladder match then near_match prefix rule (never corrects text)."""
    qv = _ladder_variants(quote)
    hv = _ladder_variants(haystack)
    for name, q, h in zip(_LADDER_NAMES, qv, hv):
        if q and q in h:
            start = h.find(q)
            return QuoteMatch(VERBATIM_EXACT, name, name, (start, start + len(q)))
    total = len(qv[4].split())
    pref = longest_prefix_words(qv[4], hv[6])
    detail = f"{pref}/{total}w prefix"
    if total and pref >= total - NEAR_MAX_MISSING_WORDS and pref / total >= NEAR_MIN_RATIO:
        return QuoteMatch(NEAR_MATCH, None, detail, None)
    return QuoteMatch(UNSUPPORTED, None, detail, None)


def check_slots(slots: dict) -> list:
    """Gate C: return (slot, reason) rows for missing / empty PICO slots."""
    rows = []
    for slot in ("population", "intervention", "comparator", "outcome", "follow_up"):
        value = slots.get(slot)
        if value is None or (isinstance(value, str) and not value.strip()):
            rows.append((slot, "empty value, not NOT_REPORTED"))
    return rows


@dataclass
class VerifierOutcome:
    """Combined Gate A/B/C outcome for one finding candidate."""

    verdict: str
    matched_variant: Optional[str]
    detail: str
    span: Optional[tuple]
    source_hedge_terms: list = field(default_factory=list)
    claim_hedge_terms: list = field(default_factory=list)
    fidelity: str = FAITHFUL
    slot_rows: list = field(default_factory=list)

    @property
    def rejected(self) -> bool:
        """Fail-closed: unsupported grounding or overclaim rejects the finding."""
        return self.verdict == UNSUPPORTED or self.fidelity == OVERCLAIM

    @property
    def reject_class(self) -> Optional[str]:
        if self.fidelity == OVERCLAIM:
            return OVERCLAIM
        if self.verdict == UNSUPPORTED:
            return UNSUPPORTED
        return None


def audit_finding(quote: str, claim: str, slots: dict, haystack: str) -> VerifierOutcome:
    """Run Gates A+B+C for one finding candidate against one grounding text.

    ``quote`` / ``claim`` are used verbatim (never rewritten); ``slots`` is
    the raw PICO slot mapping; ``haystack`` is the normalized grounding text
    (block or page norm). Gate B fidelity: overclaim = quote hedge dropped
    from the claim (hard reject); add_hedge = claim adds a hedge (counted,
    never rejected); faithful otherwise.
    """
    match = classify_quote(quote, haystack)
    qh = sorted(hedge_set(quote))
    sh = sorted(hedge_set(claim))
    if set(qh) - set(sh):
        fidelity = OVERCLAIM
    elif set(sh) - set(qh):
        fidelity = ADD_HEDGE
    else:
        fidelity = FAITHFUL
    return VerifierOutcome(
        verdict=match.verdict,
        matched_variant=match.matched_variant,
        detail=match.detail,
        span=match.span,
        source_hedge_terms=qh,
        claim_hedge_terms=sh,
        fidelity=fidelity,
        slot_rows=check_slots(slots),
    )


def _selftest() -> int:
    """Builtin self-check (scripts/measure discipline, design L7/D6)."""
    cases = [
        ("V0", "Patient outcomes improved.", "Patient outcomes improved."),
        ("V1", "cafe\u0301 trial", "caf\u00e9 trial done"),
        ("V2", "\ufb01x the kit", "fix the kit now"),
        ("V3", "outcomes   improved.", "outcomes improved."),
        ("V4", "IQR 6,838\u201319,034", "IQR 6,838-19,034 was stable"),
        ("V5", "car- dioprotective", "the cardioprotective effect"),
        ("V6", "meta-analysis", "a metaanalysis of trials"),
    ]
    rc = 0
    for want_variant, quote, hay in cases:
        got = classify_quote(quote, hay)
        ok = got.verdict == VERBATIM_EXACT and got.matched_variant == want_variant
        print(f"SELFTEST {want_variant:<3} got={str(got.matched_variant):<4} {'ok' if ok else 'FAIL'}")
        rc |= 0 if ok else 1
    checks = [
        (NEAR_MATCH, " ".join(["word"] * 27) + " tail", " ".join(["word"] * 27) + " different ending words here"),
        (UNSUPPORTED, " ".join(["word"] * 10) + " tail", " ".join(["word"] * 7) + " entirely different ending words"),
        (OVERCLAIM, "may reduce risk", "reduces risk clearly"),
        (FAITHFUL, "may reduce risk", "may reduce risk"),
        (ADD_HEDGE, "reduces risk clearly", "may reduce risk"),
    ]
    for want, quote, claim_or_hay in checks[:2]:
        got = classify_quote(quote, claim_or_hay)
        ok = got.verdict == want
        print(f"SELFTEST {want:<15} got={got.verdict:<15} {'ok' if ok else 'FAIL'}")
        rc |= 0 if ok else 1
    for want_f, quote, claim in checks[2:]:
        got = audit_finding(quote, claim, {"population": "p", "intervention": "i", "comparator": "c", "outcome": "o", "follow_up": "f"}, "hay")
        ok = got.fidelity == want_f
        print(f"SELFTEST {want_f:<15} got={got.fidelity:<15} {'ok' if ok else 'FAIL'}")
        rc |= 0 if ok else 1
    return rc


if __name__ == "__main__":
    raise SystemExit(_selftest())
