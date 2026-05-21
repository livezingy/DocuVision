"""KIE 字段计数、填充率与生产验收规则（契约与云测共用）。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# 生产 hit：至少一个关键键非空（且整体不是仅 raw_output）
_PRODUCTION_KEY_HINTS: Dict[str, List[str]] = {
    "invoice": ["invoice_number", "total", "seller_name", "invoice_date"],
    "receipt": ["total", "merchant_name", "receipt_date", "receipt_number"],
    "id_card": ["name", "id_number"],
    "passport": ["passport_number", "name"],
    "bank_card": ["bank_card_number", "bank_name"],
}

# id_card 专项精度（KIE-ACCEPT-003）：在 002 之上要求号码字段可用
_ID_CARD_ID_NUMBER_RE = re.compile(r"^[0-9]{17}[0-9Xx]$")
_ID_CARD_PRECISION_KEYS: List[str] = ["name", "id_number"]


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def is_raw_output_only(fields: Dict[str, Any]) -> bool:
    if not isinstance(fields, dict) or not fields:
        return False
    keys = set(fields.keys())
    if keys == {"raw_output"}:
        return True
    if len(keys) == 1 and "raw_output" in keys:
        return True
    return False


def count_meaningful_kie_fields(fields: Dict[str, Any]) -> int:
    """统计有效字段数：排除 raw_output；空字符串不计入。"""
    if not isinstance(fields, dict):
        return 0
    if is_raw_output_only(fields):
        return 0
    n = 0
    for key, value in fields.items():
        if key == "raw_output":
            continue
        if _is_non_empty(value):
            n += 1
    return n


def compute_fill_confidence(fields: Dict[str, Any], document_type: str) -> float:
    """启发式置信度：关键提示字段填充比例（0.0～1.0）。"""
    hints = _PRODUCTION_KEY_HINTS.get(document_type, [])
    if not hints or not isinstance(fields, dict) or is_raw_output_only(fields):
        return 0.0
    filled = sum(1 for k in hints if _is_non_empty(fields.get(k)))
    return round(filled / len(hints), 4)


def evaluate_kie_contract(kie_stage: str, kie_fields_count: int) -> Tuple[bool, str]:
    """Rule KIE-ACCEPT-001：流水线契约（允许 completed + 0 字段）。"""
    if kie_stage != "completed":
        return False, f"stage_not_completed:{kie_stage}"
    if kie_fields_count < 0:
        return False, f"invalid_negative_count:{kie_fields_count}"
    if kie_fields_count == 0:
        return True, "completed_with_zero_fields_allowed"
    return True, "completed_with_field_hits"


def evaluate_kie_production_hit(
    document_type: str,
    fields: Dict[str, Any],
) -> Tuple[bool, str, List[str]]:
    """Rule KIE-ACCEPT-002：生产质量（须有关键字段且非 raw_output-only）。"""
    doc = (document_type or "").strip().lower()
    if not isinstance(fields, dict) or not fields:
        return False, "empty_fields", []
    if is_raw_output_only(fields):
        return False, "raw_output_only", []
    hints = _PRODUCTION_KEY_HINTS.get(doc, [])
    if not hints:
        return False, f"unsupported_doc_type:{doc}", []
    matched = [k for k in hints if _is_non_empty(fields.get(k))]
    if matched:
        return True, "production_hit", matched
    return False, "no_required_keys_filled", []


def is_valid_id_card_number(value: Any) -> bool:
    """18 位公民身份号码格式（不校验校验位算法）。"""
    if not isinstance(value, str):
        return False
    text = value.strip()
    return bool(_ID_CARD_ID_NUMBER_RE.match(text))


def evaluate_kie_id_card_precision(
    document_type: str,
    fields: Dict[str, Any],
) -> Tuple[bool, str, List[str]]:
    """Rule KIE-ACCEPT-003：id_card 字段精度（name + 合法 id_number 均非空）。"""
    doc = (document_type or "").strip().lower()
    if doc != "id_card":
        return True, "not_id_card", []
    if not isinstance(fields, dict) or not fields or is_raw_output_only(fields):
        return False, "empty_or_raw_output_only", []

    matched: List[str] = []
    name = fields.get("name")
    if _is_non_empty(name):
        matched.append("name")

    id_number = fields.get("id_number")
    if is_valid_id_card_number(id_number):
        matched.append("id_number")

    if "name" in matched and "id_number" in matched:
        return True, "id_card_precision_hit", matched
    if "name" in matched and "id_number" not in matched:
        return False, "id_number_missing_or_invalid", matched
    if "id_number" in matched:
        return False, "name_missing", matched
    return False, "name_and_id_number_missing", []
