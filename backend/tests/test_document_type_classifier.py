"""Tests for document type classifier."""

from app.services.document_type_classifier import classify_document


def test_classify_invoice_text() -> None:
    result = classify_document("", text_hint="Invoice Number INV-001 Bill To Customer")
    assert result["document_type"] == "invoice"
    assert result["confidence"] > 0
