"""UieToAzureMapper 单测：UIE 输出 → BaseField 映射。"""

import json
from pathlib import Path

import pytest

from app.services.kie.azure_schema import BaseField
from app.services.kie.uie_to_azure import UieToAzureMapper
from app.services.kie.word_indexer import WordIndexer

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def indexer():
    layout = json.loads((FIXTURES / "pp_structure_invoice.json").read_text(encoding="utf-8"))
    return WordIndexer.from_layout(layout)


@pytest.fixture
def uie_result():
    return json.loads((FIXTURES / "uie_output_invoice.json").read_text(encoding="utf-8"))


class TestAzureName:
    def test_strips_aliases(self):
        assert UieToAzureMapper.azure_name("InvoiceId|发票号码|Invoice No") == "InvoiceId"
        assert UieToAzureMapper.azure_name("InvoiceTotal") == "InvoiceTotal"


class TestMapField:
    def test_string_field_has_value_string(self, indexer):
        mapper = UieToAzureMapper(indexer)
        bf = mapper.map_field(
            "InvoiceId",
            {"text": "12345678", "start": 80, "end": 88, "probability": 0.98},
        )
        assert bf.type == "string"
        assert bf.content == "12345678"
        assert bf.valueString == "12345678"
        assert bf.confidence == pytest.approx(0.98)
        assert len(bf.boundingRegions) >= 1
        assert len(bf.spans) == 1

    def test_date_field_has_value_date(self, indexer):
        mapper = UieToAzureMapper(indexer)
        bf = mapper.map_field(
            "InvoiceDate",
            {"text": "19/2/2024", "start": 122, "end": 131, "probability": 0.95},
        )
        assert bf.type == "date"
        assert bf.valueDate == "2024-02-19"

    def test_currency_field_has_value_currency(self, indexer):
        mapper = UieToAzureMapper(indexer)
        bf = mapper.map_field(
            "InvoiceTotal",
            {"text": "GBP 180.00", "start": 321, "end": 331, "probability": 0.93},
        )
        assert bf.type == "currency"
        assert bf.valueCurrency is not None
        assert bf.valueCurrency.amount == 180.0
        assert bf.valueCurrency.currencyCode == "GBP"

    def test_offset_invalid_falls_back_to_text_lookup(self, indexer):
        mapper = UieToAzureMapper(indexer)
        bf = mapper.map_field(
            "InvoiceId",
            {"text": "12345678", "start": -1, "end": -1, "probability": 0.7},
        )
        assert bf.content == "12345678"
        assert len(bf.boundingRegions) >= 1


class TestMapUieResult:
    def test_passes_relations_through(self, indexer, uie_result):
        mapper = UieToAzureMapper(indexer)
        out = mapper.map_uie_result(uie_result)
        # Items 含 relations，原样透传 raw hits 列表
        assert "Items" in out
        assert isinstance(out["Items"], list)
        assert "relations" in out["Items"][0]

    def test_maps_single_value_fields(self, indexer, uie_result):
        mapper = UieToAzureMapper(indexer)
        out = mapper.map_uie_result(uie_result)
        for k in ["InvoiceId", "InvoiceDate", "InvoiceTotal", "VendorName"]:
            assert k in out, f"missing {k}"
            assert isinstance(out[k], BaseField)

    def test_empty_input(self, indexer):
        mapper = UieToAzureMapper(indexer)
        assert mapper.map_uie_result([]) == {}
        assert mapper.map_uie_result(None) == {}
        assert mapper.map_uie_result([{}]) == {}
