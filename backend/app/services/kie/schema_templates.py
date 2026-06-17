"""Custom KIE schema templates and document_type=custom support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

_TEMPLATE_DIR = Path(__file__).resolve().parent / "kie_configs" / "templates"
_runtime_templates: Dict[str, Dict[str, Any]] = {}


def list_templates() -> List[str]:
    names = set(_runtime_templates.keys())
    if _TEMPLATE_DIR.is_dir():
        for path in _TEMPLATE_DIR.glob("*.yaml"):
            names.add(path.stem)
    return sorted(names)


def load_template(template_id: str) -> Optional[Dict[str, Any]]:
    tid = (template_id or "").strip()
    if not tid:
        return None
    if tid in _runtime_templates:
        return _runtime_templates[tid]
    path = _TEMPLATE_DIR / f"{tid}.yaml"
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else None


def save_template(template_id: str, schema: Dict[str, Any]) -> None:
    tid = (template_id or "").strip()
    if not tid:
        raise ValueError("template_id required")
    _runtime_templates[tid] = schema
    _TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _TEMPLATE_DIR / f"{tid}.yaml"
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(schema, fh, allow_unicode=False, sort_keys=False)


def resolve_custom_schema(options: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Resolve custom schema from options (template_id or inline kie_custom_schema)."""
    doc_type = str(options.get("document_type", "") or "").strip().lower()
    if doc_type not in {"custom", "template"}:
        template_id = options.get("kie_template_id")
        if template_id:
            return load_template(str(template_id))
        return None

    inline = options.get("kie_custom_schema")
    if isinstance(inline, str):
        try:
            inline = json.loads(inline)
        except json.JSONDecodeError:
            return None
    if isinstance(inline, dict):
        return inline

    template_id = options.get("kie_template_id")
    if template_id:
        return load_template(str(template_id))
    return None
