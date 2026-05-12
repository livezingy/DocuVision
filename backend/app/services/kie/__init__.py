"""Document Key Information Extraction (KIE) sub-package.

主线使用 Qwen2.5-VL（``KieManager`` + ``kie_configs/*.yaml``）。本包保留与 Azure 对齐的
schema / 类型化工具，供测试与后续规范化复用。
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

__all__ = [
    "AddressValue",
    "BaseField",
    "BoundingRegion",
    "CurrencyValue",
    "FIELD_TYPE_MAP",
    "KieResult",
    "Span",
    "ValueTyper",
]
