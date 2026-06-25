"""HITL depth policy by document_type and vertical template."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from app.services.kie.field_validation import default_rules_for_document_type

FULL_DOC_TYPES = frozenset({"invoice", "receipt", "id_card", "passport", "bank_card"})
LITE_TEMPLATES = frozenset({"bank_statement", "invoice_line_items"})

LITE_VALIDATION_RULES: Dict[str, Dict[str, str]] = {
    "transaction_date": {"type": "date"},
    "amount": {"type": "currency"},
    "unit_price": {"type": "currency"},
    "line_total": {"type": "currency"},
    "balance": {"type": "currency"},
}

TEMPLATE_SCHEMA_FIELDS: Dict[str, Tuple[str, ...]] = {
    "bank_statement": ("transaction_date", "description", "amount", "balance"),
    "invoice_line_items": ("line_description", "quantity", "unit_price", "line_total"),
}


@dataclass
class HitlPolicy:
    profile: str
    validation_rules: Dict[str, Dict[str, str]] = field(default_factory=dict)
    enable_enqueue: bool = False
    schema_field_names: Tuple[str, ...] = ()

    def should_enqueue(self, validation: Dict[str, Any], enable_hitl: bool = True) -> bool:
        if not enable_hitl or not self.enable_enqueue:
            return False
        return not bool(validation.get("validation_passed", True))


def _resolve_template_name(options: Dict[str, Any]) -> str:
    template = str(options.get("table_template") or "").strip().lower()
    if template:
        return template
    doc = str(options.get("document_type") or "").strip().lower()
    if doc == "custom":
        return str(
            options.get("kie_template") or options.get("template_id") or ""
        ).strip().lower()
    return ""


def resolve_hitl_policy(options: Dict[str, Any]) -> HitlPolicy:
    doc = str(options.get("document_type") or "auto").strip().lower()
    template = _resolve_template_name(options)

    if doc in FULL_DOC_TYPES:
        return HitlPolicy(
            profile="full",
            validation_rules=default_rules_for_document_type(doc),
            enable_enqueue=True,
        )

    if doc == "custom" and template in LITE_TEMPLATES:
        return HitlPolicy(
            profile="lite",
            validation_rules=dict(LITE_VALIDATION_RULES),
            enable_enqueue=True,
            schema_field_names=TEMPLATE_SCHEMA_FIELDS.get(template, ()),
        )

    return HitlPolicy(profile="off", validation_rules={}, enable_enqueue=False)
