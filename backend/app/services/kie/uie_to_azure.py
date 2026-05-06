"""UIE 输出 → Azure BaseField 映射器。

PaddleNLP UIE Taskflow 单批输出形如：
    [{
        "InvoiceId|发票号码|...": [
            {"text": "12345678", "start": 91, "end": 99, "probability": 0.98}
        ],
        "Items|商品行|...": [
            {"text": "Wood Pallet", "start": 200, "end": 211,
             "probability": 0.92,
             "relations": {
                 "Quantity|数量|...": [{"text": "1.00", ...}],
                 ...
             }}
        ],
        ...
    }]

UieToAzureMapper.map_uie_result() 将单值字段映射为 BaseField；
关系字段（含 relations 的 hits）原样透传，由 ItemsAggregator 处理。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.kie.azure_schema import BaseField
from app.services.kie.value_typer import FIELD_TYPE_MAP, ValueTyper
from app.services.kie.word_indexer import WordIndexer


class UieToAzureMapper:
    """UIE 抽出 → BaseField 转换器。"""

    def __init__(self, indexer: WordIndexer):
        self.indexer = indexer

    @staticmethod
    def azure_name(raw_name: str) -> str:
        """从 'AzureName|中文别名|...' 取主名。"""
        return str(raw_name).split("|", 1)[0]

    def map_field(self, azure_name: str, hit: Dict[str, Any]) -> BaseField:
        """单条 UIE hit → BaseField。"""
        text = str(hit.get("text", "") or "")
        try:
            start = int(hit.get("start", 0) or 0)
            end = int(hit.get("end", start + len(text)) or 0)
        except (TypeError, ValueError):
            start, end = -1, -1
        try:
            prob = float(hit.get("probability", 0.0) or 0.0)
        except (TypeError, ValueError):
            prob = 0.0

        regions: List = []
        spans: List = []
        if start >= 0 and end > start:
            regions, spans = self.indexer.lookup_by_offset(start, end)
        if not regions:
            regions, spans = self.indexer.lookup_by_text(text)

        ftype = FIELD_TYPE_MAP.get(azure_name, "string")
        bf = BaseField(
            type=ftype,
            content=text,
            confidence=prob,
            boundingRegions=regions,
            spans=spans,
        )

        if ftype == "date":
            bf.valueDate = ValueTyper.to_date(text)
        elif ftype == "currency":
            bf.valueCurrency = ValueTyper.to_currency(text)
        elif ftype == "number":
            bf.valueNumber = ValueTyper.to_number(text)
        elif ftype == "address":
            bf.valueAddress = ValueTyper.to_address(text)
        else:
            bf.valueString = text or None

        return bf

    def map_uie_result(self, uie_result: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """整批 UIE 结果 → {azure_name: BaseField | List[hit dict]}。

        含 relations 的字段（嵌套 / 行项目）原样透传 raw hits 列表，
        交由 ItemsAggregator 进一步聚合；其余字段直接映射为 BaseField。
        """
        if not uie_result or not isinstance(uie_result, list):
            return {}
        head = uie_result[0]
        if not isinstance(head, dict):
            return {}

        out: Dict[str, Any] = {}
        for raw_name, hits in head.items():
            if not isinstance(hits, list) or not hits:
                continue
            azure_name = self.azure_name(raw_name)

            has_relations = any(
                isinstance(h, dict) and "relations" in h and h.get("relations")
                for h in hits
            )
            if has_relations:
                # 透传给 ItemsAggregator
                out[azure_name] = hits
                continue

            best = max(
                (h for h in hits if isinstance(h, dict)),
                key=lambda h: float(h.get("probability", 0.0) or 0.0),
                default=None,
            )
            if best is None:
                continue
            out[azure_name] = self.map_field(azure_name, best)

        return out
