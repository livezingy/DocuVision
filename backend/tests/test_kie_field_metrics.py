"""KIE 字段指标与验收规则单测（无模型）。"""

from app.services.kie.kie_field_metrics import (
    count_meaningful_kie_fields,
    evaluate_kie_contract,
    evaluate_kie_id_card_precision,
    evaluate_kie_production_hit,
    is_raw_output_only,
    is_valid_id_card_number,
)
from app.services.kie.KieManager import KieManager


def test_count_meaningful_excludes_raw_output_only() -> None:
    assert count_meaningful_kie_fields({"raw_output": "not json"}) == 0
    assert is_raw_output_only({"raw_output": "x"}) is True


def test_count_meaningful_counts_non_empty_schema_keys() -> None:
    fields = {"invoice_number": "A001", "total": "", "seller_name": "ACME"}
    assert count_meaningful_kie_fields(fields) == 2


def test_production_hit_invoice() -> None:
    ok, reason, keys = evaluate_kie_production_hit(
        "invoice",
        {"invoice_number": "123", "total": ""},
    )
    assert ok is True
    assert reason == "production_hit"
    assert "invoice_number" in keys


def test_production_miss_when_only_raw_output() -> None:
    ok, reason, _ = evaluate_kie_production_hit("invoice", {"raw_output": "{broken"})
    assert ok is False
    assert reason == "raw_output_only"


def test_contract_rule_unchanged() -> None:
    ok, _ = evaluate_kie_contract("completed", 0)
    assert ok is True


def test_parse_json_tolerates_markdown_fence() -> None:
    text = '说明\n```json\n{"invoice_number": "X1"}\n```\n'
    sanitized = KieManager._sanitize_json_text('{"a": 1,}')
    assert '"a": 1' in sanitized
    mgr = KieManager.__new__(KieManager)
    assert mgr._parse_json(text) == {"invoice_number": "X1"}


def test_id_card_number_format() -> None:
    assert is_valid_id_card_number("110101199001011234") is True
    assert is_valid_id_card_number("32010219880515231X") is True
    assert is_valid_id_card_number("123") is False
    assert is_valid_id_card_number("") is False


def test_id_card_precision_requires_name_and_valid_id_number() -> None:
    ok, reason, keys = evaluate_kie_id_card_precision(
        "id_card",
        {"name": "张伟", "id_number": "110101199001011234"},
    )
    assert ok is True
    assert reason == "id_card_precision_hit"
    assert set(keys) == {"name", "id_number"}


def test_id_card_precision_miss_when_only_name() -> None:
    ok, reason, keys = evaluate_kie_id_card_precision("id_card", {"name": "张伟"})
    assert ok is False
    assert reason == "id_number_missing_or_invalid"
    assert keys == ["name"]


def test_id_card_precision_not_applicable_for_invoice() -> None:
    ok, reason, _ = evaluate_kie_id_card_precision("invoice", {"invoice_number": "A1"})
    assert ok is True
    assert reason == "not_id_card"
