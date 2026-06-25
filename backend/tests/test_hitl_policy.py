"""Tests for HITL policy profiles."""

from app.services.hitl_policy import resolve_hitl_policy


def test_hitl_policy_full_for_invoice():
    policy = resolve_hitl_policy({"document_type": "invoice"})
    assert policy.profile == "full"
    assert policy.enable_enqueue is True
    assert "invoice_date" in policy.validation_rules or "total" in policy.validation_rules


def test_hitl_policy_lite_for_custom_bank_statement():
    policy = resolve_hitl_policy(
        {"document_type": "custom", "table_template": "bank_statement"}
    )
    assert policy.profile == "lite"
    assert policy.enable_enqueue is True
    assert "transaction_date" in policy.schema_field_names


def test_hitl_policy_off_for_general():
    policy = resolve_hitl_policy({"document_type": "general"})
    assert policy.profile == "off"
    assert policy.enable_enqueue is False
    assert policy.should_enqueue({"validation_passed": False}, enable_hitl=True) is False


def test_hitl_policy_full_enqueues_on_validation_failure():
    policy = resolve_hitl_policy({"document_type": "invoice"})
    assert policy.should_enqueue({"validation_passed": False}, enable_hitl=True) is True
    assert policy.should_enqueue({"validation_passed": False}, enable_hitl=False) is False
