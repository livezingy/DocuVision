"""Customer schema -> table column mapping config (R-003/P-042 T2, AC1 backend half).

Config layer over the existing schema-template mechanism
(``schema_templates.py`` YAML store fed by POST /api/v1/kie/templates/{id}).
One template (or one inline schema) configured once on the batch options
applies to every task of the batch: ``table_step`` resolves it per task run,
maps the extracted tables, and stamps the resolved output fields on the task
result (``mapped_table_fields``) so the MappedRows export face
(``batch_export_service``) drives its columns from the mapping result.
Services domains stay decoupled: the batch export face reads stamped result
keys only and never imports the kie domain (S1b: no new cross-domain edge).

Accepted customer-schema shapes (both normalize into one config dict):
  - ``fields: [{name, aliases?}]`` — schema-template YAML shape (the
    ``kie_configs/templates/*.yaml`` shape); ``aliases`` optional
  - ``output_fields: [...]`` + ``aliases: {field: [...]}`` — mapping-table
    shape (mirrors docuvision_core ``TABLE_TEMPLATES``)
A field's own name is always an implicit alias. Fail-closed: an unusable
schema yields ``None`` / empty rows — never an exception, never a guessed
column set.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.services.kie.schema_templates import load_template

__all__ = [
    "apply_schema_mapping",
    "build_mapping_config",
    "map_table_rows",
    "resolve_mapping_config",
]

# Template-id option keys, in resolution order. ``kie_template`` /
# ``template_id`` are the custom-document fallback keys (same gating as
# orchestration/steps/extraction.py table_step: only consulted when
# document_type is custom/template) — mirrors resolve_custom_schema semantics.
_TEMPLATE_OPTION_KEYS = ("table_template", "kie_template_id")
_CUSTOM_DOC_FALLBACK_KEYS = ("kie_template", "template_id")
_CUSTOM_DOC_TYPES = ("custom", "template")


def _normalize_header(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def build_mapping_config(schema: Any, template_id: str = "") -> Optional[Dict[str, Any]]:
    """Normalize a customer schema document into a column-mapping config.

    Returns ``None`` when the schema carries no usable output fields
    (fail-closed: callers skip mapping instead of guessing columns).
    """
    if not isinstance(schema, dict):
        return None
    output_fields: List[str] = []
    aliases: Dict[str, Tuple[str, ...]] = {}

    def _add_field(name: str, extra: Sequence[Any] = ()) -> None:
        name = str(name or "").strip()
        if not name or name in aliases:
            return
        output_fields.append(name)
        merged: List[str] = [name]
        for alias in extra:
            alias = str(alias or "").strip()
            if alias and alias not in merged:
                merged.append(alias)
        aliases[name] = tuple(merged)

    fields = schema.get("fields")
    if isinstance(fields, list) and fields:
        for entry in fields:
            if not isinstance(entry, dict):
                continue
            extra = entry.get("aliases")
            if not isinstance(extra, (list, tuple)):
                extra = ()
            _add_field(str(entry.get("name") or ""), extra)
    elif isinstance(schema.get("output_fields"), list):
        for name in schema["output_fields"]:
            _add_field(str(name or ""))
        declared = schema.get("aliases")
        if isinstance(declared, dict):
            for field, extra in declared.items():
                fname = str(field or "").strip()
                if fname in aliases and isinstance(extra, (list, tuple)):
                    merged = list(aliases[fname]) + [
                        str(a or "").strip() for a in extra if str(a or "").strip()
                    ]
                    aliases[fname] = tuple(dict.fromkeys(merged))

    if not output_fields:
        return None
    return {
        "template_id": str(template_id or "").strip(),
        "output_fields": output_fields,
        "aliases": aliases,
    }


def resolve_mapping_config(options: Any) -> Optional[Dict[str, Any]]:
    """Resolve the batch-wide mapping config from options (one config -> whole batch).

    Resolution order (first usable hit wins): inline ``kie_custom_schema``
    (dict or JSON string), then a template id from ``table_template`` /
    ``kie_template_id`` loaded through the schema-template YAML store, then
    the custom-document fallback keys. Unresolvable -> ``None``.
    """
    opts = options if isinstance(options, dict) else {}
    inline = opts.get("kie_custom_schema")
    if isinstance(inline, str) and inline.strip():
        try:
            inline = json.loads(inline)
        except json.JSONDecodeError:
            inline = None
    if isinstance(inline, dict):
        config = build_mapping_config(inline)
        if config is not None:
            return config

    template_id = ""
    doc_type = str(opts.get("document_type") or "").strip().lower()
    for key in _TEMPLATE_OPTION_KEYS + _CUSTOM_DOC_FALLBACK_KEYS:
        if key in _CUSTOM_DOC_FALLBACK_KEYS and doc_type not in _CUSTOM_DOC_TYPES:
            continue
        template_id = str(opts.get(key) or "").strip()
        if template_id:
            break
    if not template_id:
        return None
    loaded = load_template(template_id)
    if not isinstance(loaded, dict):
        return None
    return build_mapping_config(loaded, template_id=template_id)


def _alias_lookup(config: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for field, aliases in (config.get("aliases") or {}).items():
        for alias in aliases:
            out[_normalize_header(alias)] = field
    return out


def _table_data_rows(table: Dict[str, Any]) -> Tuple[List[str], List[List[Any]]]:
    data = table.get("data")
    if isinstance(data, list) and data:
        if isinstance(data[0], (list, tuple)):
            header = [str(c) for c in data[0]]
            rows = [list(r) for r in data[1:] if isinstance(r, (list, tuple))]
            return header, rows
    headers = table.get("headers") or []
    rows = table.get("rows") or []
    if headers:
        return [str(h) for h in headers], [list(r) for r in rows]
    return [], []


def _header_map(headers: Sequence[str], lookup: Dict[str, str]) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    for idx, header in enumerate(headers):
        field = lookup.get(_normalize_header(str(header)))
        if field:
            mapping[idx] = field
    return mapping


def map_table_rows(
    table: Dict[str, Any],
    config: Dict[str, Any],
    *,
    table_index: int = 0,
) -> List[Dict[str, Any]]:
    """Map one extracted table to the config's output fields.

    Row dicts carry the same shape as docuvision_core's mapped rows
    (provenance keys ``template`` / ``source_table_index`` / ``page`` /
    ``row_index`` + one key per field, every configured field present).
    Rows without any field value are dropped (fail-closed: no alias hit ->
    no mapping, never a fabricated column).
    """
    output_fields = [str(f) for f in (config.get("output_fields") or []) if str(f).strip()]
    if not output_fields:
        return []
    lookup = _alias_lookup(config)
    headers, rows = _table_data_rows(table)
    header_map = _header_map(headers, lookup)
    data_rows = rows
    if not header_map and rows:
        first_row_map = _header_map([str(c) for c in rows[0]], lookup)
        if len(first_row_map) >= 2:
            header_map = first_row_map
            data_rows = rows[1:]

    page = int(table.get("page") or 1)
    template_id = str(config.get("template_id") or "")
    mapped: List[Dict[str, Any]] = []
    for row_index, row in enumerate(data_rows):
        record: Dict[str, Any] = {
            "template": template_id,
            "source_table_index": table_index,
            "page": page,
            "row_index": row_index,
        }
        for col_idx, cell in enumerate(row):
            field = header_map.get(col_idx)
            if not field:
                continue
            text = str(cell or "").strip()
            if text:
                record[field] = text
        if any(record.get(f) for f in output_fields):
            for field in output_fields:
                record.setdefault(field, "")
            mapped.append(record)
    return mapped


def apply_schema_mapping(
    tables: Any,
    config: Any,
) -> List[Dict[str, Any]]:
    """Apply a resolved mapping config across all extracted tables."""
    if not isinstance(config, dict) or not isinstance(tables, list):
        return []
    out: List[Dict[str, Any]] = []
    for idx, table in enumerate(tables):
        if isinstance(table, dict):
            out.extend(map_table_rows(table, config, table_index=idx))
    return out
