"""Runtime KIE query fields (extend-only schema merge, Azure Query Fields aligned)."""

from __future__ import annotations

import copy
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import yaml

logger = logging.getLogger(__name__)

KIE_QUERY_FIELDS_MAX = 20
FIELD_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
DESCRIPTION_MAX_LEN = 200

_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions", re.I),
    re.compile(r"disregard\s+(the\s+)?(system|above)", re.I),
    re.compile(r"you\s+are\s+now\s+", re.I),
    re.compile(r"<\s*/?\s*system\s*>", re.I),
)

_DEFAULT_KIE_CONFIG_DIR = Path(__file__).resolve().parent / "kie_configs"

KIE_SUPPORTED_DOC_TYPES = frozenset(
    {"invoice", "receipt", "id_card", "passport", "bank_card", "custom"}
)


class QueryFieldsError(ValueError):
    """Validation failure for kie_query_fields."""

    def __init__(self, error_code: str, message: str) -> None:
        self.error_code = error_code
        super().__init__(message)


def _strip_control_chars(text: str) -> str:
    return "".join(ch for ch in text if ch >= " " or ch in "\n\t")


def _sanitize_description(raw: Optional[str], field_name: str) -> str:
    if not raw or not str(raw).strip():
        return f"User-defined field: {field_name}"
    desc = _strip_control_chars(str(raw).strip())
    for pat in _INJECTION_PATTERNS:
        if pat.search(desc):
            logger.warning("KIE query field description blocked pattern | field=%s", field_name)
            raise QueryFieldsError(
                "unsafe_description",
                f"Field '{field_name}' description contains disallowed instruction-like text",
            )
    if len(desc) > DESCRIPTION_MAX_LEN:
        desc = desc[:DESCRIPTION_MAX_LEN]
    return desc


def _normalize_field_entry(entry: Any, index: int) -> Dict[str, str]:
    if isinstance(entry, str):
        name = entry.strip()
        if not name:
            raise QueryFieldsError("invalid_field_name", f"Query field at index {index} is empty")
        return {"name": name, "description": _sanitize_description(None, name)}

    if not isinstance(entry, dict):
        raise QueryFieldsError(
            "invalid_field_entry",
            f"Query field at index {index} must be a string or object with 'name'",
        )

    name = str(entry.get("name", "") or "").strip()
    if not name:
        raise QueryFieldsError("invalid_field_name", f"Query field at index {index} missing 'name'")
    desc_raw = entry.get("description")
    return {"name": name, "description": _sanitize_description(desc_raw, name)}


def parse_kie_query_fields(raw: Any) -> List[Dict[str, str]]:
    """Parse API/option payload into normalized query field specs."""
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise QueryFieldsError("invalid_json", f"kie_query_fields is not valid JSON: {exc}") from exc

    if not isinstance(raw, list):
        raise QueryFieldsError("invalid_type", "kie_query_fields must be a JSON array")

    seen: Set[str] = set()
    out: List[Dict[str, str]] = []
    for i, item in enumerate(raw):
        spec = _normalize_field_entry(item, i)
        name = spec["name"]
        if not FIELD_NAME_RE.match(name):
            raise QueryFieldsError(
                "invalid_field_name",
                f"Field '{name}' must match [A-Za-z][A-Za-z0-9_]*",
            )
        key_lower = name.lower()
        if key_lower in seen:
            raise QueryFieldsError("duplicate_query_field", f"Duplicate query field name '{name}'")
        seen.add(key_lower)
        out.append(spec)

    if len(out) > KIE_QUERY_FIELDS_MAX:
        raise QueryFieldsError(
            "too_many_fields",
            f"At most {KIE_QUERY_FIELDS_MAX} query fields allowed per request",
        )
    return out


def load_base_schema(type_id: str, config_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Load schema dict from kie_configs/{type_id}.yaml."""
    root = Path(config_dir) if config_dir is not None else _DEFAULT_KIE_CONFIG_DIR
    path = root / f"{type_id}.yaml"
    if not path.is_file():
        raise QueryFieldsError("unknown_document_type", f"No KIE config for document_type '{type_id}'")
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    schema = config.get("schema")
    if not isinstance(schema, dict):
        raise QueryFieldsError("invalid_schema", f"KIE config for '{type_id}' has no schema dict")
    return schema


def _base_schema_keys(schema: Dict[str, Any]) -> Set[str]:
    return {str(k) for k in schema.keys()}


def build_merged_schema(
    base_schema: Dict[str, Any],
    query_fields: Sequence[Dict[str, str]],
) -> Dict[str, Any]:
    """Return deep-copied base schema with query field descriptions appended (extend-only)."""
    merged = copy.deepcopy(base_schema)
    base_keys = _base_schema_keys(base_schema)
    for spec in query_fields:
        name = spec["name"]
        if name in base_keys:
            raise QueryFieldsError(
                "duplicate_field",
                f"Query field '{name}' conflicts with built-in schema key",
            )
        merged[name] = spec["description"]
    return merged


def validate_and_prepare_query_fields(
    document_type: str,
    raw_query_fields: Any,
    *,
    config_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """
    Parse query fields and merge with YAML schema for document_type.
    Returns (normalized_specs, merged_schema).
    """
    doc_type = str(document_type or "").strip().lower()
    if doc_type not in KIE_SUPPORTED_DOC_TYPES:
        raise QueryFieldsError(
            "unsupported_document_type",
            f"document_type '{doc_type}' does not support kie_query_fields",
        )
    specs = parse_kie_query_fields(raw_query_fields)
    if not specs:
        base = load_base_schema(doc_type, config_dir)
        return [], base
    base = load_base_schema(doc_type, config_dir)
    merged = build_merged_schema(base, specs)
    return list(specs), merged


def attach_kie_query_fields_to_options(options: Dict[str, Any]) -> None:
    """
    Validate and normalize kie_query_fields on task options (mutates options).
    Raises QueryFieldsError when query fields are invalid or incompatible with options.
    """
    raw = options.get("kie_query_fields")
    enable_kie = bool(options.get("enable_kie", False))
    doc_type = str(options.get("document_type", "auto") or "auto").strip().lower()

    try:
        specs = parse_kie_query_fields(raw)
    except QueryFieldsError:
        raise

    if specs and not enable_kie:
        raise QueryFieldsError(
            "query_fields_require_kie",
            "kie_query_fields requires enable_kie=true",
        )
    if specs and doc_type not in KIE_SUPPORTED_DOC_TYPES:
        raise QueryFieldsError(
            "unsupported_document_type",
            f"document_type '{doc_type}' does not support kie_query_fields",
        )

    if enable_kie and doc_type in KIE_SUPPORTED_DOC_TYPES and specs:
        normalized, merged = validate_and_prepare_query_fields(doc_type, specs)
        options["kie_query_fields"] = normalized
        options["kie_query_field_names"] = [s["name"] for s in normalized]
        options["kie_merged_schema"] = merged
    else:
        options["kie_query_fields"] = []
        options["kie_query_field_names"] = []
        options["kie_merged_schema"] = None


def list_filled_query_fields(
    fields: Dict[str, Any],
    requested_names: Sequence[str],
) -> List[str]:
    """Names in requested_names that have a non-empty meaningful value in fields."""
    if not isinstance(fields, dict):
        return []
    filled: List[str] = []
    for name in requested_names:
        val = fields.get(name)
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        if isinstance(val, (list, dict)) and len(val) == 0:
            continue
        if name == "raw_output":
            continue
        filled.append(name)
    return filled
