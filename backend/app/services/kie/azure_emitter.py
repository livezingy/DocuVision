"""AzureSchemaEmitter：组装 KieResult 顶层结构。

当前实现为薄壳：直接以 Mapper + ItemsAggregator 的输出 + 平均 confidence
组装 KieResult 并产出 view.fields dict。后续若需要在不同 document_type
间做更复杂的字段后处理（如 invoice 总额校验、id_card 校验码等），
统一在此 emitter 内做。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.kie.azure_schema import BaseField, KieResult


class AzureSchemaEmitter:
    """组装 KieResult。"""

    def __init__(self, document_type: str):
        self.document_type = document_type

    def build(
        self,
        single_fields: Dict[str, BaseField],
        items: Optional[List[BaseField]] = None,
        payment_details: Optional[List[BaseField]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KieResult:
        fields: Dict[str, BaseField] = {
            k: v for k, v in single_fields.items() if isinstance(v, BaseField)
        }

        if items:
            fields["Items"] = BaseField(
                type="array",
                content="",
                confidence=_avg_confidence(items),
                valueArray=list(items),
            )
        if payment_details:
            fields["PaymentDetails"] = BaseField(
                type="array",
                content="",
                confidence=_avg_confidence(payment_details),
                valueArray=list(payment_details),
            )

        avg_conf = _avg_confidence(list(fields.values()))
        return KieResult(
            documentType=self.document_type,
            fields=fields,
            confidence=avg_conf,
            metadata=metadata or {},
        )


def _avg_confidence(items: List[BaseField]) -> float:
    confs = [bf.confidence for bf in items if isinstance(bf, BaseField) and bf.confidence > 0]
    if not confs:
        return 0.0
    return sum(confs) / len(confs)
