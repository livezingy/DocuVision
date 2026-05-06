"""DocumentKIEService 主流程单测（mock 子进程，不真实加载 PaddleNLP）。"""

import asyncio
import json
from pathlib import Path

import pytest

from app.services.kie_service import DocumentKIEService

FIXTURES = Path(__file__).parent / "kie" / "fixtures"


class _MockEngine:
    """模拟常驻 UIE worker，绕过 paddlenlp 加载。"""

    load_ms = 0

    def __init__(self, uie_output):
        self._uie_output = uie_output

    def analyze_text(self, text):
        return self._uie_output


def _load_layout():
    return json.loads((FIXTURES / "pp_structure_invoice.json").read_text(encoding="utf-8"))


def _load_uie():
    return json.loads((FIXTURES / "uie_output_invoice.json").read_text(encoding="utf-8"))


def test_extract_fields_returns_view_compatible_dict(monkeypatch):
    svc = DocumentKIEService()
    monkeypatch.setattr(
        DocumentKIEService,
        "_get_engine",
        lambda self, dt: _MockEngine(_load_uie()),
    )

    async def run_test():
        res = await svc.extract_fields(
            "somepath.pdf",
            "invoice",
            preprocessed_image_path="/tmp/preproc.jpg",
            layout=_load_layout(),
            table_meta={"tables_returned": 0},
            tables=[],
        )

        assert isinstance(res, dict)
        # view.fields 兼容
        fields = res["fields"]
        assert isinstance(fields, dict)
        assert "InvoiceId" in fields
        assert "InvoiceDate" in fields
        assert "InvoiceTotal" in fields
        assert fields["InvoiceDate"].get("valueDate") == "2024-02-19"
        assert fields["InvoiceTotal"]["valueCurrency"]["amount"] == 180.0

        # confidence_avg / metadata
        assert res["confidence_avg"] > 0
        assert res["metadata"]["items_source"] in {"uie_relation", "table_heuristic", "none"}

        # 行项目应被聚合
        items = fields.get("Items")
        assert items is not None
        assert items["type"] == "array"
        assert isinstance(items.get("valueArray"), list)
        assert len(items["valueArray"]) >= 1

        # debug_input 透传
        assert res["debug_input"]["preprocessed_image_path"] == "/tmp/preproc.jpg"
        assert res["debug_input"]["ocr_text_length"] > 0

    asyncio.run(run_test())


def test_extract_fields_empty_layout_short_circuits(monkeypatch):
    svc = DocumentKIEService()
    called = {"n": 0}

    class _ShouldNotBeCalled:
        load_ms = 0

        def analyze_text(self, text):
            called["n"] += 1
            return []

    monkeypatch.setattr(
        DocumentKIEService,
        "_get_engine",
        lambda self, dt: _ShouldNotBeCalled(),
    )

    async def run_test():
        res = await svc.extract_fields(
            "x.pdf",
            "invoice",
            layout={"elements": []},
        )
        assert res["fields"] == {}
        assert res["metadata"]["reason"] == "empty_ocr_text"
        assert called["n"] == 0  # 子进程未被触发

    asyncio.run(run_test())


@pytest.mark.parametrize("doc_type", ["invoice", "receipt", "id_card"])
def test_extract_fields_routes_by_document_type(monkeypatch, doc_type):
    svc = DocumentKIEService()
    monkeypatch.setattr(
        DocumentKIEService,
        "_get_engine",
        lambda self, dt: _MockEngine(_load_uie()),
    )

    async def run_test():
        res = await svc.extract_fields(
            "x.pdf",
            doc_type,
            layout=_load_layout(),
        )
        assert isinstance(res, dict)
        assert "fields" in res

    asyncio.run(run_test())
