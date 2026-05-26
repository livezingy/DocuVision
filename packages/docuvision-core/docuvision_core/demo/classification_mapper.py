"""Apply configurable external → internal classification mappings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_mapping_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"rules": [], "default_internal_code": "UNMAPPED"}
    return json.loads(path.read_text(encoding="utf-8"))


def _match_rule(value: str, rule: Dict[str, Any]) -> bool:
    if not value:
        return False
    match_type = (rule.get("match") or "exact").lower()
    pattern = str(rule.get("external") or "")
    if match_type == "exact":
        return value.strip().lower() == pattern.strip().lower()
    if match_type == "contains":
        return pattern.strip().lower() in value.strip().lower()
    if match_type == "prefix":
        return value.strip().lower().startswith(pattern.strip().lower())
    return False


def map_category(
    external_category: str,
    config: Dict[str, Any],
) -> Dict[str, str]:
    default_code = str(config.get("default_internal_code") or "UNMAPPED")
    default_label = str(config.get("default_internal_label") or "Unmapped")
    for rule in config.get("rules") or []:
        if _match_rule(external_category, rule):
            return {
                "internal_code": str(rule.get("internal_code") or default_code),
                "internal_label": str(rule.get("internal_label") or default_label),
                "mapping_rule_id": str(rule.get("id") or ""),
            }
    return {
        "internal_code": default_code,
        "internal_label": default_label,
        "mapping_rule_id": "",
    }


def apply_classification_mappings(
    transactions: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    mapped: List[Dict[str, Any]] = []
    for tx in transactions:
        external = str(tx.get("category") or tx.get("description") or "")
        mapping = map_category(external, config)
        mapped.append({**tx, **mapping})
    return mapped
