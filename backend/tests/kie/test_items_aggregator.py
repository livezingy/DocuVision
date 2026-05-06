"""ItemsAggregator 单测：UIE 关系优先 / 表格 fallback / 阈值切换。"""

import json
from pathlib import Path

import pytest

from app.services.kie.azure_schema import BaseField
from app.services.kie.items_aggregator import ItemsAggregator
from app.services.kie.uie_to_azure import UieToAzureMapper
from app.services.kie.word_indexer import WordIndexer

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def indexer():
    layout = json.loads((FIXTURES / "pp_structure_invoice.json").read_text(encoding="utf-8"))
    return WordIndexer.from_layout(layout)


@pytest.fixture
def mapper(indexer):
    return UieToAzureMapper(indexer)


@pytest.fixture
def uie_full():
    return json.loads((FIXTURES / "uie_output_invoice.json").read_text(encoding="utf-8"))


class TestUieRelationPath:
    def test_aggregates_uie_items(self, indexer, mapper, uie_full):
        agg = ItemsAggregator(indexer, mapper, tables=[]).aggregate(
            uie_full[0]["Items|商品行|发票明细"]
        )
        assert agg["items_source"] == "uie_relation"
        assert len(agg["Items"]) == 1
        item = agg["Items"][0]
        assert isinstance(item, BaseField)
        assert item.type == "object"
        assert item.valueObject is not None
        assert "Description" in item.valueObject
        assert "Quantity" in item.valueObject

    def test_no_items_returns_none_source(self, indexer, mapper):
        agg = ItemsAggregator(indexer, mapper, tables=[]).aggregate(None)
        assert agg["Items"] == []
        assert agg["items_source"] == "none"


class TestTableFallback:
    def _build_table(self, rows):
        return {"rows": rows}

    def test_table_heuristic_when_uie_empty(self, indexer, mapper):
        tables = [
            self._build_table(
                [
                    ["Description", "Qty", "Unit Price", "Amount", "VAT %", "VAT Amount"],
                    ["Wood Pallet", "1.00", "100.00", "100.00", "20.00", "20.00"],
                    ["Steel rod(s)", "2.00", "25.00", "50.00", "20.00", "10.00"],
                ]
            )
        ]
        agg = ItemsAggregator(indexer, mapper, tables=tables).aggregate(None)
        assert agg["items_source"] == "table_heuristic"
        assert len(agg["Items"]) == 2
        first = agg["Items"][0]
        assert first.valueObject is not None
        assert first.valueObject["Description"].content == "Wood Pallet"
        assert first.valueObject["Quantity"].valueNumber == 1.0

    def test_uie_below_threshold_falls_back_to_tables(self, indexer, mapper):
        # UIE 仅命中 1 行，table 有 4 行，1 < 4×0.5=2 → 走 table_heuristic
        sparse_uie = [
            {
                "text": "Wood Pallet",
                "probability": 0.7,
                "relations": {
                    "Description|品名": [{"text": "Wood Pallet", "start": -1, "end": -1, "probability": 0.7}],
                },
            }
        ]
        rows = [["Description", "Qty"]] + [[f"Item {i}", str(i)] for i in range(1, 5)]
        tables = [{"rows": rows}]
        agg = ItemsAggregator(indexer, mapper, tables=tables).aggregate(sparse_uie)
        assert agg["items_source"] == "table_heuristic"
        assert len(agg["Items"]) == 4

    def test_no_description_column_skipped(self, indexer, mapper):
        # 没有 Description / Item 列时不进入 fallback
        tables = [{"rows": [["Foo", "Bar"], ["a", "b"]]}]
        agg = ItemsAggregator(indexer, mapper, tables=tables).aggregate(None)
        assert agg["Items"] == []
        assert agg["items_source"] == "none"


class TestPaymentDetails:
    def test_aggregates_payment_relations(self, indexer, mapper):
        payment_raw = [
            {
                "text": "Bank: Contoso Bank",
                "probability": 0.85,
                "relations": {
                    "IBAN|国际银行账号": [
                        {"text": "GB29 1234 5678 9012 3456 78", "start": -1, "end": -1, "probability": 0.9}
                    ],
                    "SWIFT|SWIFT 代码|SWIFT Code": [
                        {"text": "ABCDGB2L", "start": -1, "end": -1, "probability": 0.88}
                    ],
                },
            }
        ]
        agg = ItemsAggregator(indexer, mapper, tables=[]).aggregate(None, payment_raw)
        assert len(agg["PaymentDetails"]) == 1
        pay = agg["PaymentDetails"][0]
        assert pay.valueObject is not None
        assert "IBAN" in pay.valueObject
        assert "SWIFT" in pay.valueObject
