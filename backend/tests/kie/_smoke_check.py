"""KIE 模块 stdlib smoke check（不依赖 pytest）。

仅用作本地无 pytest 环境时快速验证关键路径；正式 CI 应使用 pytest 套件。
运行：
    python -m tests.kie._smoke_check
任何 assert 失败将以非零退出码终止。
"""
from __future__ import annotations

import asyncio
import json
import sys
import traceback
from pathlib import Path


def _add_app_to_path() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(backend_dir))


def _stub_app_packages() -> None:
    """避开 app/services/__init__.py 的副作用 import（loguru 等重依赖）。

    手动注入空的 namespace package：app / app.services / app.services.kie /
    app.services.kie.schemas，让子模块按需懒加载。
    """
    import types

    backend_dir = Path(__file__).resolve().parents[2]
    pkg_paths = {
        "app": backend_dir / "app",
        "app.services": backend_dir / "app" / "services",
        "app.services.kie": backend_dir / "app" / "services" / "kie",
        "app.services.kie.schemas": backend_dir / "app" / "services" / "kie" / "schemas",
    }
    for name, p in pkg_paths.items():
        if name in sys.modules:
            continue
        m = types.ModuleType(name)
        m.__path__ = [str(p)]
        sys.modules[name] = m


_add_app_to_path()
_stub_app_packages()


def check_value_typer() -> None:
    from app.services.kie.value_typer import ValueTyper

    assert ValueTyper.to_date("19/2/2024") == "2024-02-19"
    assert ValueTyper.to_date("2024-02-19") == "2024-02-19"
    assert ValueTyper.to_date("19-Feb-2024") == "2024-02-19"
    assert ValueTyper.to_date("not-a-date") is None

    cv = ValueTyper.to_currency("GBP 180.00")
    assert cv is not None and cv.amount == 180.0 and cv.currencyCode == "GBP"
    cv2 = ValueTyper.to_currency("£100")
    assert cv2 is not None and cv2.amount == 100.0 and cv2.currencyCode == "GBP"

    assert ValueTyper.to_number("1,024.50") == 1024.5
    print("[OK] value_typer")


def check_word_indexer() -> dict:
    from app.services.kie.word_indexer import WordIndexer

    fixtures_dir = Path(__file__).parent / "fixtures"
    layout = json.loads((fixtures_dir / "pp_structure_invoice.json").read_text(encoding="utf-8"))
    indexer = WordIndexer.from_layout(layout)

    # content 按 reading_order 拼接
    assert "Invoice No 12345678" in indexer.content
    assert "Total GBP 180.00" in indexer.content

    # offset 与 content char index 对齐
    for w in indexer.words:
        assert indexer.content[w.offset : w.offset + w.length] == w.text, (
            f"offset misaligned at {w.offset}: {w.text!r}"
        )

    # 反查
    idx = indexer.content.find("12345678")
    regions, spans = indexer.lookup_by_offset(idx, idx + 8)
    assert len(regions) >= 1 and len(spans) == 1
    assert len(regions[0].polygon) == 8

    print(f"[OK] word_indexer (content_len={len(indexer.content)}, words={len(indexer.words)})")
    return {"indexer": indexer, "layout": layout}


def check_uie_to_azure(indexer) -> dict:
    from app.services.kie.uie_to_azure import UieToAzureMapper
    from app.services.kie.azure_schema import BaseField

    fixtures_dir = Path(__file__).parent / "fixtures"
    uie_result = json.loads((fixtures_dir / "uie_output_invoice.json").read_text(encoding="utf-8"))

    mapper = UieToAzureMapper(indexer)
    mapped = mapper.map_uie_result(uie_result)

    for k in ("InvoiceId", "InvoiceDate", "InvoiceTotal"):
        assert k in mapped, f"missing {k}"
        assert isinstance(mapped[k], BaseField), f"{k} is not BaseField: {type(mapped[k])}"

    assert mapped["InvoiceDate"].valueDate == "2024-02-19"
    assert mapped["InvoiceTotal"].valueCurrency is not None
    assert mapped["InvoiceTotal"].valueCurrency.amount == 180.0
    assert mapped["InvoiceTotal"].valueCurrency.currencyCode == "GBP"

    assert isinstance(mapped["Items"], list), "Items 应原样透传 raw hits 列表"
    print("[OK] uie_to_azure")
    return {"mapper": mapper, "mapped": mapped}


def check_items_aggregator(indexer, mapper, mapped) -> None:
    from app.services.kie.items_aggregator import ItemsAggregator

    items_raw = mapped["Items"]
    agg = ItemsAggregator(indexer, mapper, tables=[]).aggregate(items_raw)
    assert agg["items_source"] == "uie_relation"
    assert len(agg["Items"]) == 1
    item = agg["Items"][0]
    assert item.type == "object" and item.valueObject is not None
    assert "Description" in item.valueObject
    assert "Quantity" in item.valueObject

    # table fallback
    tables = [
        {
            "rows": [
                ["Description", "Qty", "Unit Price", "Amount"],
                ["Wood Pallet", "1.00", "100.00", "100.00"],
                ["Steel rod(s)", "2.00", "25.00", "50.00"],
            ]
        }
    ]
    agg2 = ItemsAggregator(indexer, mapper, tables=tables).aggregate(None)
    assert agg2["items_source"] == "table_heuristic"
    assert len(agg2["Items"]) == 2

    print("[OK] items_aggregator")


def check_kie_service_e2e() -> None:
    from app.services.kie_service import DocumentKIEService

    fixtures_dir = Path(__file__).parent / "fixtures"
    layout = json.loads((fixtures_dir / "pp_structure_invoice.json").read_text(encoding="utf-8"))
    uie_output = json.loads((fixtures_dir / "uie_output_invoice.json").read_text(encoding="utf-8"))

    class _MockEngine:
        load_ms = 0

        def analyze_text(self, text: str):
            return uie_output

    svc = DocumentKIEService()
    # monkey patch _get_engine (无需 pytest fixture)
    svc._get_engine = lambda dt: _MockEngine()  # type: ignore[assignment]

    async def run():
        return await svc.extract_fields(
            "x.pdf",
            "invoice",
            preprocessed_image_path="/tmp/preproc.jpg",
            layout=layout,
            table_meta={"tables_returned": 0},
            tables=[],
        )

    res = asyncio.run(run())
    fields = res["fields"]
    assert "InvoiceId" in fields
    assert "InvoiceDate" in fields
    assert fields["InvoiceDate"]["valueDate"] == "2024-02-19"
    assert fields["InvoiceTotal"]["valueCurrency"]["amount"] == 180.0
    assert fields["InvoiceTotal"]["valueCurrency"]["currencyCode"] == "GBP"
    assert "Items" in fields and fields["Items"]["type"] == "array"
    assert res["confidence_avg"] > 0
    assert res["metadata"]["items_source"] == "uie_relation"
    print(
        f"[OK] kie_service.extract_fields | fields={len(fields)} "
        f"confidence_avg={res['confidence_avg']:.3f} items={res['items_count']}"
    )


def main() -> int:
    try:
        check_value_typer()
        ctx1 = check_word_indexer()
        ctx2 = check_uie_to_azure(ctx1["indexer"])
        check_items_aggregator(ctx1["indexer"], ctx2["mapper"], ctx2["mapped"])
        check_kie_service_e2e()
        print("\nAll smoke checks passed.")
        return 0
    except AssertionError as exc:
        traceback.print_exc()
        print(f"\nSMOKE FAILURE: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        traceback.print_exc()
        print(f"\nSMOKE ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
