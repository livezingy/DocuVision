"""QwenDocumentKIEService 单测：mock KieManager，不加载 HF 权重。"""

import asyncio
import os
from pathlib import Path

import pytest
from PIL import Image

from app.services.kie_qwen_service import QwenDocumentKIEService


class _FakeKieManager:
    def __init__(self) -> None:
        self.last_image: str = ""
        self.last_type: str = ""

    def extract(self, image_path: str, option_type: str, lang=None):
        self.last_image = image_path
        self.last_type = option_type
        return {
            "type": option_type,
            "fields": {
                "invoice_number": "INV-001",
                "items": [{"description": "A", "amount": "1"}],
            },
        }


def _patch_init_manager(fake: _FakeKieManager):
    def _impl(self: QwenDocumentKIEService) -> None:
        self._manager = fake
        self._init_wall_ms = 12

    return _impl


def test_extract_fields_returns_kie_step_compatible_dict(monkeypatch, tmp_path: Path) -> None:
    fake = _FakeKieManager()
    monkeypatch.setattr(QwenDocumentKIEService, "_init_manager", _patch_init_manager(fake))

    img_path = tmp_path / "one.png"
    Image.new("RGB", (4, 4), color="white").save(img_path)

    async def run_test():
        svc = QwenDocumentKIEService()
        res = await svc.extract_fields(
            str(img_path),
            "invoice",
            preprocessed_image_path=str(img_path),
            layout={"elements": []},
            table_meta={"tables_returned": 0},
            tables=[],
        )
        assert isinstance(res, dict)
        fields = res["fields"]
        assert fields["invoice_number"] == "INV-001"
        assert len(fields["items"]) == 1
        assert res["items_count"] == 1
        assert res["confidence_avg"] > 0.0
        assert res["metadata"]["engine"] == "qwen2.5-vl"
        assert res["metadata"]["resolved_document_type"] == "invoice"
        assert res["metadata"]["items_source"] == "n/a"
        assert res["debug_input"]["vl_image_path"] == str(img_path)

    asyncio.run(run_test())


def test_extract_fields_missing_image_returns_empty(monkeypatch) -> None:
    fake = _FakeKieManager()
    monkeypatch.setattr(QwenDocumentKIEService, "_init_manager", _patch_init_manager(fake))

    async def run_test():
        svc = QwenDocumentKIEService()
        res = await svc.extract_fields(
            "/nonexistent/path/nope.pdf",
            "invoice",
            preprocessed_image_path=None,
        )
        assert res["fields"] == {}
        assert res["metadata"].get("reason") == "kie_image_missing"
        assert fake.last_image == ""

    asyncio.run(run_test())


@pytest.mark.parametrize(
    "doc_type",
    ["invoice", "receipt", "id_card", "passport", "bank_card"],
)
def test_extract_fields_routes_document_type(monkeypatch, tmp_path: Path, doc_type: str) -> None:
    fake = _FakeKieManager()
    monkeypatch.setattr(QwenDocumentKIEService, "_init_manager", _patch_init_manager(fake))

    img_path = tmp_path / f"{doc_type}.png"
    Image.new("RGB", (2, 2)).save(img_path)

    async def run_test():
        svc = QwenDocumentKIEService()
        res = await svc.extract_fields(str(img_path), doc_type)
        assert res["metadata"]["resolved_document_type"] == doc_type
        assert fake.last_type == doc_type

    asyncio.run(run_test())


def test_pdf_raster_fallback_uses_temp_png(monkeypatch, tmp_path: Path) -> None:
    fake = _FakeKieManager()
    monkeypatch.setattr(QwenDocumentKIEService, "_init_manager", _patch_init_manager(fake))

    import fitz

    pdf_path = tmp_path / "doc.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hi")
    doc.save(str(pdf_path))
    doc.close()

    async def run_test():
        svc = QwenDocumentKIEService()
        res = await svc.extract_fields(str(pdf_path), "invoice", preprocessed_image_path=None)
        assert res["fields"]["invoice_number"] == "INV-001"
        assert fake.last_image.endswith(".png")
        assert os.path.isfile(fake.last_image) is False

    asyncio.run(run_test())
