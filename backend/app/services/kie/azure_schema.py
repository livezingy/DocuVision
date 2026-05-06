"""与 Azure Document Intelligence prebuilt-invoice 对齐的 dataclass 定义。

字段命名严格使用 Azure 公共命名（CamelCase）：
- Span.offset / Span.length
- BoundingRegion.pageNumber / BoundingRegion.polygon
- BaseField.type / content / boundingRegions / confidence / spans / valueXxx
- CurrencyValue.amount / currencyCode
- AddressValue.streetAddress / city / state / postalCode / countryRegion / ...

KieResult.to_view_fields() 输出可直接写入 envelope.view.fields。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class Span:
    offset: int
    length: int


@dataclass
class BoundingRegion:
    pageNumber: int
    polygon: List[float]


@dataclass
class CurrencyValue:
    amount: float
    currencyCode: Optional[str] = None


@dataclass
class AddressValue:
    streetAddress: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postalCode: Optional[str] = None
    countryRegion: Optional[str] = None
    houseNumber: Optional[str] = None
    road: Optional[str] = None
    poBox: Optional[str] = None


FieldType = Literal["string", "date", "currency", "number", "address", "object", "array"]


@dataclass
class BaseField:
    """与 Azure DocumentField 对齐的字段表示。

    使用 valueXxx 单值约定：每个字段实例只填一个 valueXxx
    （valueObject / valueArray 用于嵌套结构）。
    """

    type: FieldType
    content: str
    boundingRegions: List[BoundingRegion] = field(default_factory=list)
    confidence: float = 0.0
    spans: List[Span] = field(default_factory=list)
    valueString: Optional[str] = None
    valueDate: Optional[str] = None
    valueNumber: Optional[float] = None
    valueCurrency: Optional[CurrencyValue] = None
    valueAddress: Optional[AddressValue] = None
    valueObject: Optional[Dict[str, "BaseField"]] = None
    valueArray: Optional[List["BaseField"]] = None

    def to_dict(self) -> Dict[str, Any]:
        """递归转 dict，去除 None 与空容器 (空 list / 空 dict)。"""
        return _prune(asdict(self))


@dataclass
class KieResult:
    documentType: str
    fields: Dict[str, BaseField] = field(default_factory=dict)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_view_fields(self) -> Dict[str, Any]:
        """转为可写入 envelope.view.fields 的纯 dict。"""
        return {name: bf.to_dict() for name, bf in self.fields.items() if isinstance(bf, BaseField)}


def _prune(obj: Any) -> Any:
    """递归剔除 None / 空 list / 空 dict，保留 0 与空字符串。"""
    if isinstance(obj, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in obj.items():
            pv = _prune(v)
            # 保留 0、0.0、空字符串；过滤 None / 空 list / 空 dict
            if pv is None:
                continue
            if isinstance(pv, (list, dict)) and len(pv) == 0:
                continue
            cleaned[k] = pv
        return cleaned
    if isinstance(obj, list):
        return [_prune(x) for x in obj if x is not None]
    return obj
