"""Default KIE validation rules by document type (shared leaf, I-1/P-038).

Pure static mapping consumed by both ``kie.field_validation`` (re-exports it)
and ``hitl_policy`` (resolves its validation_rules from the same table), so
the two domains can never drift on what "default rules for document type X"
means. Zero outbound ``app.*`` imports (L1 strength A). Promoted verbatim
from ``kie/field_validation.py`` in runs/split batch 2 to break the
hitl<->kie cycle (frozen edges #8/#9).
"""

from __future__ import annotations

from typing import Dict


def default_rules_for_document_type(document_type: str) -> Dict[str, Dict[str, str]]:
    doc = (document_type or "").strip().lower()
    if doc == "invoice":
        return {
            "invoice_date": {"type": "date"},
            "date": {"type": "date"},
            "total": {"type": "currency"},
            "total_amount": {"type": "currency"},
            "subtotal": {"type": "currency"},
            "tax": {"type": "currency"},
        }
    if doc == "receipt":
        return {
            "date": {"type": "date"},
            "total": {"type": "currency"},
            "subtotal": {"type": "currency"},
            "tax": {"type": "currency"},
        }
    if doc == "id_card":
        return {"id_number": {"type": "regex", "pattern": r"^\d{18}$"}}
    if doc == "passport":
        return {"passport_number": {"type": "regex", "pattern": r"^[A-Za-z0-9]{6,12}$"}}
    if doc == "bank_card":
        return {
            "card_number": {"type": "regex", "pattern": r"^[\d\s-]{13,19}$"},
            "expiry_date": {"type": "date"},
        }
    if doc == "custom":
        return {
            "transaction_date": {"type": "date"},
            "amount": {"type": "currency"},
            "unit_price": {"type": "currency"},
            "line_total": {"type": "currency"},
            "balance": {"type": "currency"},
        }
    return {}
