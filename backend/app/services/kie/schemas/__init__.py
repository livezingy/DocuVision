"""按 document_type 路由的 PaddleNLP UIE schema 集合。

每条 schema 字段名采用 'AzureName|中文别名|常见英文别名' 形式：
- 第一段（| 前）= Azure 主名（用于反查映射）
- 其余段 = uie-m-base 在多语种环境下提升命中率的别名

调用 Taskflow 时直接传 SCHEMAS[document_type] 即可。
"""

from app.services.kie.schemas.id_card import ID_CARD_SCHEMA
from app.services.kie.schemas.invoice import INVOICE_SCHEMA
from app.services.kie.schemas.receipt import RECEIPT_SCHEMA

SCHEMAS = {
    "invoice": INVOICE_SCHEMA,
    "id_card": ID_CARD_SCHEMA,
    "receipt": RECEIPT_SCHEMA,
}

__all__ = ["INVOICE_SCHEMA", "ID_CARD_SCHEMA", "RECEIPT_SCHEMA", "SCHEMAS"]
