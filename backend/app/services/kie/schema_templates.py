"""Custom KIE schema templates and document_type=custom support."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

_TEMPLATE_DIR = Path(__file__).resolve().parent / "kie_configs" / "templates"
_runtime_templates: Dict[str, Dict[str, Any]] = {}

# Template ids are used directly as filenames, so reject anything that could
# escape the template directory (path traversal / absolute paths / separators).
_TEMPLATE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _validate_template_id(template_id: str) -> str:
    """Return a sanitized template id or raise ValueError on unsafe input."""
    tid = (template_id or "").strip()
    if not tid or not _TEMPLATE_ID_RE.match(tid):
        raise ValueError(f"Invalid template_id: {tid!r}")
    # Defense in depth: reject any path-shaped fragment even if the regex missed it.
    if "/" in tid or "\\" in tid or tid in {"", ".", ".."} or tid.startswith("."):
        raise ValueError(f"Invalid template_id: {tid!r}")
    return tid


def list_templates() -> List[str]:
    names = set(_runtime_templates.keys())
    if _TEMPLATE_DIR.is_dir():
        for path in _TEMPLATE_DIR.glob("*.yaml"):
            names.add(path.stem)
    return sorted(names)


def load_template(template_id: str) -> Optional[Dict[str, Any]]:
    try:
        tid = _validate_template_id(template_id)
    except ValueError:
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
    tid = _validate_template_id(template_id)
    _runtime_templates[tid] = schema
    _TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _TEMPLATE_DIR / f"{tid}.yaml"
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(schema, fh, allow_unicode=False, sort_keys=False)


def resolve_custom_schema(options: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Resolve custom schema from options (template_id or inline kie_custom_schema).

    NOTE: Not wired into the analyze pipeline in v1.4. ``custom`` /
    ``template`` document types are removed from ``KIE_SUPPORTED_DOC_TYPES``
    and ``kie_step`` does not call this function. Reserved for v1.5+ /
    customization work that will expose ``kie_custom_schema`` and
    ``kie_template_id`` on the analyze Form and connect this resolver in
    ``kie_step``. Kept (with tests) so the contract is not silently lost.
    """
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
