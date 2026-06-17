"""Generic KIE field validation engine (date / currency / regex)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional


_DATE_PATTERNS = [
    r"^\d{4}-\d{2}-\d{2}$",
    r"^\d{2}/\d{2}/\d{4}$",
    r"^\d{2}-\d{2}-\d{4}$",
]

_CURRENCY_PATTERN = re.compile(r"^[\$€£]?\s*-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?$")


def validate_date(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    for pattern in _DATE_PATTERNS:
        if re.match(pattern, text):
            return True
    return False


def validate_currency(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return bool(_CURRENCY_PATTERN.match(text))


def validate_regex(value: Any, pattern: str) -> bool:
    text = str(value or "").strip()
    if not text or not pattern:
        return False
    try:
        return bool(re.match(pattern, text))
    except re.error:
        return False


def validate_kie_fields(
    fields: Dict[str, Any],
    rules: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Validate extracted KIE fields against optional rules.

    rules example: {"invoice_date": {"type": "date"}, "total": {"type": "currency"}}
    """
    rules = rules or {}
    field_results: Dict[str, Any] = {}
    passed = 0
    failed = 0

    for name, value in (fields or {}).items():
        rule = rules.get(name, {})
        rule_type = (rule.get("type") or "").strip().lower()
        ok = True
        if rule_type == "date":
            ok = validate_date(value)
        elif rule_type == "currency":
            ok = validate_currency(value)
        elif rule_type == "regex" and rule.get("pattern"):
            ok = validate_regex(value, rule["pattern"])
        field_results[name] = {"valid": ok, "value": value, "rule": rule_type or "none"}
        if ok:
            passed += 1
        else:
            failed += 1

    return {
        "validation_passed": failed == 0,
        "validation_fields_passed": passed,
        "validation_fields_failed": failed,
        "validation_field_results": field_results,
    }


def default_rules_for_document_type(document_type: str) -> Dict[str, Dict[str, str]]:
    doc = (document_type or "").strip().lower()
    if doc == "invoice":
        return {
            "invoice_date": {"type": "date"},
            "date": {"type": "date"},
            "total": {"type": "currency"},
            "total_amount": {"type": "currency"},
        }
    if doc == "receipt":
        return {"date": {"type": "date"}, "total": {"type": "currency"}}
    return {}
