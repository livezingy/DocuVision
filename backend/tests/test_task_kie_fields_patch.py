"""Tests for KIE field write-back service."""

from app.services.kie_fields_update import apply_kie_fields_to_task


def test_apply_kie_fields_updates_validation():
    task = {
        "options": {"document_type": "invoice"},
        "result": {
            "kie_fields": {"total": "bad"},
            "view": {"fields": {"total": "bad"}},
        },
    }

    validation = apply_kie_fields_to_task(
        task,
        {"total": "$100.00", "invoice_date": "2024-01-15"},
    )

    assert task["result"]["kie_fields"]["total"] == "$100.00"
    assert task["result"]["view"]["fields"]["total"] == "$100.00"
    assert validation.get("manual_reviewed") is True
    assert "validation_field_results" in validation
