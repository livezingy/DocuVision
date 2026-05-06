"""Items / PaymentDetails 聚合器（行项目 + 付款信息）。

策略：
- Tier 1（首选）：消费 UIE 嵌套 schema 输出，每行 hit 含 relations 子字段
  → 直接组装为 Azure InvoiceItem (BaseField type='object')。
- Tier 2（fallback）：当 Tier 1 命中数 < (表格行数 × 0.5) 时，转用
  `ctx['result']['tables']` 走启发式列名匹配。
- 输出 items_source ∈ {'uie_relation', 'table_heuristic', 'none'}。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.services.kie.azure_schema import BaseField
from app.services.kie.uie_to_azure import UieToAzureMapper
from app.services.kie.word_indexer import WordIndexer

# 表格列名（小写匹配） → Azure 字段
_COLUMN_ALIAS = {
    "description": "Description",
    "item": "Description",
    "items": "Description",
    "品名": "Description",
    "项目": "Description",
    "qty": "Quantity",
    "quantity": "Quantity",
    "数量": "Quantity",
    "unit price": "UnitPrice",
    "unit": "UnitPrice",
    "单价": "UnitPrice",
    "amount": "Amount",
    "amount gbp": "Amount",
    "金额": "Amount",
    "vat %": "TaxRate",
    "tax rate": "TaxRate",
    "税率": "TaxRate",
    "vat amount": "Tax",
    "tax": "Tax",
    "vat": "Tax",
    "税额": "Tax",
}


class ItemsAggregator:
    def __init__(
        self,
        indexer: WordIndexer,
        mapper: UieToAzureMapper,
        tables: Optional[List[Dict[str, Any]]] = None,
    ):
        self.indexer = indexer
        self.mapper = mapper
        self.tables = tables or []

    def aggregate(
        self,
        uie_items_raw: Optional[List[Dict[str, Any]]],
        uie_payment_raw: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """返回 {'Items': List[BaseField], 'PaymentDetails': List[BaseField], 'items_source': str}。"""
        items, source = self._aggregate_items(uie_items_raw)
        payment = self._aggregate_with_relations(uie_payment_raw)
        return {
            "Items": items,
            "PaymentDetails": payment,
            "items_source": source,
        }

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------
    def _aggregate_items(
        self, uie_items_raw: Optional[List[Dict[str, Any]]]
    ) -> Tuple[List[BaseField], str]:
        tier1 = self._items_from_uie(uie_items_raw)
        table_row_count = self._estimated_table_row_count()

        if tier1 and (table_row_count == 0 or len(tier1) >= table_row_count * 0.5):
            return tier1, "uie_relation"

        tier2 = self._items_from_tables()
        if tier2:
            return tier2, "table_heuristic"
        if tier1:
            return tier1, "uie_relation"
        return [], "none"

    def _items_from_uie(self, uie_items_raw: Optional[List[Dict[str, Any]]]) -> List[BaseField]:
        if not uie_items_raw:
            return []
        return self._aggregate_with_relations(uie_items_raw)

    def _items_from_tables(self) -> List[BaseField]:
        out: List[BaseField] = []
        for tbl in self.tables:
            rows = self._extract_rows(tbl)
            if not rows or len(rows) < 2:
                continue

            header = [str(c).strip().lower() for c in rows[0]]
            col_map: Dict[int, str] = {}
            for i, h in enumerate(header):
                # 精确匹配优先；其次包含匹配
                if h in _COLUMN_ALIAS:
                    col_map[i] = _COLUMN_ALIAS[h]
                    continue
                for alias_key, azure_field in _COLUMN_ALIAS.items():
                    if alias_key and alias_key in h:
                        col_map[i] = azure_field
                        break
            if "Description" not in col_map.values():
                continue

            for row in rows[1:]:
                sub: Dict[str, BaseField] = {}
                for i, cell in enumerate(row):
                    azure = col_map.get(i)
                    if not azure:
                        continue
                    text = str(cell).strip()
                    if not text:
                        continue
                    bf = self.mapper.map_field(
                        azure,
                        {"text": text, "start": -1, "end": -1, "probability": 0.5},
                    )
                    sub[azure] = bf
                if sub:
                    out.append(
                        BaseField(
                            type="object",
                            content="",
                            confidence=0.5,
                            valueObject=sub,
                        )
                    )
        return out

    @staticmethod
    def _extract_rows(tbl: Dict[str, Any]) -> List[List[Any]]:
        """归一化表格行：兼容 rows / cells / html 等不同表示。"""
        if not isinstance(tbl, dict):
            return []
        rows = tbl.get("rows")
        if isinstance(rows, list) and rows and isinstance(rows[0], list):
            return rows
        cells = tbl.get("cells")
        if isinstance(cells, list) and cells and isinstance(cells[0], list):
            return cells
        # cells: [{row, col, text}, ...] 形式
        if isinstance(cells, list) and cells and isinstance(cells[0], dict):
            grid: Dict[int, Dict[int, Any]] = {}
            for c in cells:
                r = int(c.get("row", c.get("row_index", 0)) or 0)
                col = int(c.get("col", c.get("col_index", 0)) or 0)
                grid.setdefault(r, {})[col] = c.get("text", c.get("content", ""))
            sorted_rows = []
            for r in sorted(grid.keys()):
                row_dict = grid[r]
                sorted_rows.append([row_dict[k] for k in sorted(row_dict.keys())])
            return sorted_rows
        return []

    def _estimated_table_row_count(self) -> int:
        total = 0
        for tbl in self.tables:
            rows = self._extract_rows(tbl)
            if rows and len(rows) >= 2:
                total += len(rows) - 1  # 减去表头
        return total

    # ------------------------------------------------------------------
    # 通用：带 relations 的 hit → BaseField (type='object')
    # ------------------------------------------------------------------
    def _aggregate_with_relations(
        self, raw_hits: Optional[List[Dict[str, Any]]]
    ) -> List[BaseField]:
        if not raw_hits:
            return []
        out: List[BaseField] = []
        for hit in raw_hits:
            if not isinstance(hit, dict):
                continue
            relations = hit.get("relations") or {}
            if not isinstance(relations, dict) or not relations:
                continue
            sub: Dict[str, BaseField] = {}
            for sub_name_raw, sub_hits in relations.items():
                if not isinstance(sub_hits, list) or not sub_hits:
                    continue
                sub_azure = UieToAzureMapper.azure_name(sub_name_raw)
                best = max(
                    (h for h in sub_hits if isinstance(h, dict)),
                    key=lambda h: float(h.get("probability", 0.0) or 0.0),
                    default=None,
                )
                if best is None:
                    continue
                sub[sub_azure] = self.mapper.map_field(sub_azure, best)
            if not sub:
                continue
            try:
                conf = float(hit.get("probability", 0.0) or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
            out.append(
                BaseField(
                    type="object",
                    content=str(hit.get("text", "") or ""),
                    confidence=conf,
                    valueObject=sub,
                )
            )
        return out
