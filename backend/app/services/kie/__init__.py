"""Document Key Information Extraction (KIE) sub-package.

基于 PaddleNLP UIE (uie-m-base) 的 KIE 实现：
- azure_schema: 与 Azure prebuilt-invoice 对齐的 dataclass
- word_indexer: 从 PP-StructureV3 layout 抽 word/line + 拼全文 + offset 反查
- value_typer: Date / Currency / Number / Address 类型化转换
- uie_to_azure: UIE 输出 → BaseField 映射
- items_aggregator: Items / PaymentDetails 聚合 (Tier1 UIE 关系 / Tier2 表格 fallback)
- azure_emitter: 组装 KieResult 顶层结构
- schemas/: invoice / id_card / receipt 三套 PaddleNLP UIE schema
"""

from app.services.kie.azure_schema import (
    AddressValue,
    BaseField,
    BoundingRegion,
    CurrencyValue,
    KieResult,
    Span,
)
from app.services.kie.value_typer import FIELD_TYPE_MAP, ValueTyper
from app.services.kie.word_indexer import WordIndexer

__all__ = [
    "AddressValue",
    "BaseField",
    "BoundingRegion",
    "CurrencyValue",
    "FIELD_TYPE_MAP",
    "KieResult",
    "Span",
    "ValueTyper",
    "WordIndexer",
]
