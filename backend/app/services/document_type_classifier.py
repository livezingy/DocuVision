"""Heuristic document type classification (MVP)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

import pdfplumber

_KEYWORDS = {
    "invoice": ("invoice", "bill to", "invoice number", "tax id"),
    "receipt": ("receipt", "thank you", "subtotal", "payment"),
    "id_card": ("identity", "date of birth", "license", "passport"),
    "bank_card": ("card number", "valid thru", "credit card", "debit"),
    "passport": ("passport", "nationality", "mrz"),
}


def classify_document(file_path: str, text_hint: str = "") -> Dict[str, Any]:
    text = (text_hint or "").lower()
    if not text and Path(file_path).suffix.lower() == ".pdf":
        try:
            with pdfplumber.open(file_path) as pdf:
                if pdf.pages:
                    text = (pdf.pages[0].extract_text() or "").lower()
        except Exception:
            text = ""

    scores: Dict[str, int] = {}
    for doc_type, words in _KEYWORDS.items():
        scores[doc_type] = sum(1 for w in words if w in text)

    best = max(scores, key=scores.get) if scores else "auto"
    if scores.get(best, 0) == 0:
        return {"document_type": "auto", "confidence": 0.0, "scores": scores}
    total = sum(scores.values()) or 1
    return {
        "document_type": best,
        "confidence": round(scores[best] / total, 3),
        "scores": scores,
    }
