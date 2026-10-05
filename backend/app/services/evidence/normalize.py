"""Shared text normalizer for quote grounding (P-029 evidence layer).

Ported verbatim from the sciextract handover asset ``ingest_pdf.py``
(sha256[:12] b55620c5eb02): only the shared normalizer plus the module-level
``LIGATURES`` constant, per design §1 / D4 -- it lives inside the evidence
layer, NOT in the P-002 table domain. The verifier imports this single
implementation; KIE extraction code must never import it back
(independence discipline: normalization lives on the verification side only).
"""
from __future__ import annotations

import unicodedata

LIGATURES = {
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi",
    "\ufb04": "ffl", "\u0132": "IJ",
}


def normalize(text: str) -> str:
    """Normalizer for quote matching (NFC + ligatures + punctuation + whitespace)."""
    t = unicodedata.normalize("NFC", text)
    for k, v in LIGATURES.items():
        t = t.replace(k, v)
    # curly quotes / dashes -> ascii
    t = (t.replace("\u2018", "'").replace("\u2019", "'")
          .replace("\u201c", '"').replace("\u201d", '"')
          .replace("\u2013", "-").replace("\u2014", "-")
          .replace("\u2212", "-").replace("\u00a0", " ")
          .replace("\u00ad", ""))  # soft hyphen: invisible in print, present in text layer
    # join hyphenated line breaks: "exam-\nple" -> "example"
    t = t.replace("-\n", "")
    # collapse all whitespace runs to single space
    return " ".join(t.split())
