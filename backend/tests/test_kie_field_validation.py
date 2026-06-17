"""Tests for KIE field validation engine."""

from app.services.kie.field_validation import (
    default_rules_for_document_type,
    validate_currency,
    validate_date,
    validate_kie_fields,
)


def test_validate_date_ok() -> None:
    assert validate_date("2024-06-01") is True
    assert validate_date("bad") is False


def test_validate_currency_ok() -> None:
    assert validate_currency("$1,234.56") is True
    assert validate_currency("abc") is False


def test_validate_kie_fields_invoice() -> None:
    fields = {"invoice_date": "2024-01-15", "total": "$10.00", "vendor": "Acme"}
    rules = default_rules_for_document_type("invoice")
    result = validate_kie_fields(fields, rules)
    assert result["validation_passed"] is True
    assert result["validation_fields_failed"] == 0
