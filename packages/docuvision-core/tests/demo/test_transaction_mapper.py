"""Tests for demo transaction mapper."""

from docuvision_core.demo.classification_mapper import apply_classification_mappings, map_category
from docuvision_core.demo.transaction_mapper import (
    extract_transactions_from_kie_fields,
    extract_transactions_from_tables,
)


def test_extract_transactions_from_table_headers():
    tables = [
        {
            "table_id": "t1",
            "page": 1,
            "headers": ["Date", "Description", "Amount"],
            "rows": [["2024-01-01", "Office supplies", "120.00"]],
        }
    ]
    txs = extract_transactions_from_tables(tables)
    assert len(txs) == 1
    assert txs[0]["date"] == "2024-01-01"
    assert txs[0]["amount"] == "120.00"


def test_extract_transactions_skips_header_row_when_unlabeled():
    tables = [
        {
            "table_id": "t1",
            "page": 1,
            "headers": [],
            "rows": [
                ["Posting Date", "Memo", "Debit", "Type"],
                ["03/01/2024", "WIRE IN - CLIENT PAYMENT", "12,500.00", "Revenue"],
            ],
        }
    ]
    txs = extract_transactions_from_tables(tables)
    assert len(txs) == 1
    assert txs[0]["date"] == "03/01/2024"
    assert txs[0]["description"] == "WIRE IN - CLIENT PAYMENT"
    assert txs[0]["amount"] == "12,500.00"
    assert txs[0]["category"] == "Revenue"


def test_extract_transactions_from_kie_items():
    fields = {
        "items": [
            {"description": "Software license", "amount": "99.00", "quantity": "1"},
        ]
    }
    txs = extract_transactions_from_kie_fields(fields)
    assert len(txs) == 1
    assert txs[0]["description"] == "Software license"


def test_classification_mapping_contains_rule():
    config = {
        "default_internal_code": "UNMAPPED",
        "default_internal_label": "Unmapped",
        "rules": [
            {
                "id": "software",
                "external": "software",
                "match": "contains",
                "internal_code": "OPEX-4300",
                "internal_label": "Software",
            }
        ],
    }
    mapped = map_category("Software license fee", config)
    assert mapped["internal_code"] == "OPEX-4300"

    txs = [{"description": "Software license", "amount": "10"}]
    out = apply_classification_mappings(txs, config)
    assert out[0]["internal_code"] == "OPEX-4300"
