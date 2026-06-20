"""Aggregate batch task results into CSV / JSON / Excel exports."""

from __future__ import annotations

import csv
import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Set

from app.services.batch_service import BatchJob, BatchTask, TaskStatus

_MAX_KIE_COLUMNS = 40
_CORE_COLUMNS = [
    "file_name",
    "status",
    "document_type",
    "kie_stage",
    "kie_production_hit",
    "kie_fields_count",
    "validation_passed",
    "validation_fields_failed",
    "error",
]


def _flatten_value(value: Any, prefix: str = "") -> Dict[str, str]:
    out: Dict[str, str] = {}
    if isinstance(value, dict):
        for k, v in value.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, (dict, list)):
                out.update(_flatten_value(v, key))
            else:
                out[key] = "" if v is None else str(v)
    elif isinstance(value, list):
        out[prefix or "items"] = json.dumps(value, ensure_ascii=True)[:500]
    elif value is not None:
        out[prefix or "value"] = str(value)
    return out


def _task_kie_fields(task: BatchTask) -> Dict[str, Any]:
    if task.status != TaskStatus.COMPLETED or not isinstance(task.result, dict):
        return {}
    fields = task.result.get("kie_fields")
    if isinstance(fields, dict):
        return fields
    view = task.result.get("view")
    if isinstance(view, dict) and isinstance(view.get("fields"), dict):
        return view["fields"]
    quality = task.result.get("quality")
    if isinstance(quality, dict):
        pass
    return {}


def _task_quality(task: BatchTask) -> Dict[str, Any]:
    if not isinstance(task.result, dict):
        return {}
    q = task.result.get("quality")
    return q if isinstance(q, dict) else {}


def build_kie_csv_rows(batch: BatchJob, options: Optional[Dict[str, Any]] = None) -> tuple[List[str], List[Dict[str, str]]]:
    """Build header and row dicts for KIE aggregate CSV."""
    options = options or batch.options or {}
    doc_type_default = str(options.get("document_type", "") or "")
    validation_passed_only = bool(options.get("validation_passed_only"))

    dynamic_keys: Set[str] = set()
    rows: List[Dict[str, str]] = []

    for task in batch.tasks:
        fields = _task_kie_fields(task)
        flat = _flatten_value(fields)
        for k in flat:
            if k not in _CORE_COLUMNS:
                dynamic_keys.add(k)

    sorted_dynamic = sorted(dynamic_keys)[:_MAX_KIE_COLUMNS]
    header = list(_CORE_COLUMNS) + sorted_dynamic

    for task in batch.tasks:
        quality = _task_quality(task)
        fields = _task_kie_fields(task)
        flat = _flatten_value(fields)
        validation = {}
        if isinstance(task.result, dict):
            validation = task.result.get("kie_validation") or {}
        if not isinstance(validation, dict):
            validation = {}
        if validation_passed_only and validation.get("validation_passed") is False:
            continue
        if validation_passed_only and task.status != TaskStatus.COMPLETED:
            continue
        row: Dict[str, str] = {
            "file_name": task.file_name,
            "status": task.status.value,
            "document_type": str(
                options.get("document_type")
                or quality.get("document_type")
                or doc_type_default
            ),
            "kie_stage": str(quality.get("kie_stage", "") or ""),
            "kie_production_hit": str(quality.get("kie_production_hit", "")),
            "kie_fields_count": str(quality.get("kie_fields_count", "")),
            "validation_passed": str(validation.get("validation_passed", "")),
            "validation_fields_failed": str(validation.get("validation_fields_failed", "")),
            "error": task.error or "",
        }
        for k in sorted_dynamic:
            row[k] = flat.get(k, "")
        rows.append(row)

    return header, rows


def render_csv(header: List[str], rows: List[Dict[str, str]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=header, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def build_failure_csv_rows(batch: BatchJob) -> tuple[List[str], List[Dict[str, str]]]:
    header = ["file_name", "task_id", "status", "error", "kie_stage", "kie_error_code"]
    rows: List[Dict[str, str]] = []
    for task in batch.tasks:
        if task.status not in (TaskStatus.FAILED, TaskStatus.SKIPPED):
            continue
        quality = _task_quality(task)
        rows.append({
            "file_name": task.file_name,
            "task_id": task.task_id,
            "status": task.status.value,
            "error": task.error or "",
            "kie_stage": str(quality.get("kie_stage", "") or ""),
            "kie_error_code": str(quality.get("kie_error_code", "") or ""),
        })
    return header, rows


def build_summary_csv_rows(batch: BatchJob) -> tuple[List[str], List[Dict[str, str]]]:
    header = ["metric", "value"]
    rows = [
        {"metric": "batch_id", "value": batch.batch_id},
        {"metric": "name", "value": batch.name},
        {"metric": "status", "value": batch.status.value},
        {"metric": "total_tasks", "value": str(batch.total_tasks)},
        {"metric": "completed_tasks", "value": str(batch.completed_tasks)},
        {"metric": "failed_tasks", "value": str(batch.failed_tasks)},
        {"metric": "progress_percent", "value": str(batch.get_progress())},
    ]
    return header, rows


def _sanitize_sheet_name(name: str, used: Set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "_", name)[:28] or "Sheet"
    candidate = base
    idx = 1
    while candidate in used:
        suffix = f"_{idx}"
        candidate = f"{base[: 31 - len(suffix)]}{suffix}"
        idx += 1
    used.add(candidate)
    return candidate


def _task_tables(task: BatchTask) -> List[Dict[str, Any]]:
    if task.status != TaskStatus.COMPLETED or not isinstance(task.result, dict):
        return []
    tables = task.result.get("tables")
    return tables if isinstance(tables, list) else []


def _table_dataframe(table: Dict[str, Any]):
    import pandas as pd

    data = table.get("data")
    if not isinstance(data, list) or not data:
        return pd.DataFrame()
    if len(data) > 1 and isinstance(data[0], list):
        header = data[0]
        num_cols = len(header)
        normalized = [(row + [""] * num_cols)[:num_cols] for row in data[1:]]
        return pd.DataFrame(normalized, columns=header)
    return pd.DataFrame(data)


def _collect_mapped_table_rows(batch: BatchJob) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for task in batch.tasks:
        if task.status != TaskStatus.COMPLETED or not isinstance(task.result, dict):
            continue
        mapped = task.result.get("mapped_table_rows")
        if not isinstance(mapped, list):
            continue
        for entry in mapped:
            if isinstance(entry, dict):
                row = dict(entry)
                row["file_name"] = task.file_name
                rows.append(row)
    return rows


def build_batch_xlsx_bytes(batch: BatchJob, mode: str = "all") -> bytes:
    """Build aggregated batch workbook (summary, optional KIE sheet, per-file table sheets)."""
    import pandas as pd

    mode_norm = (mode or "all").strip().lower()
    include_kie = mode_norm in {"all", "kie", "summary"}
    include_tables = mode_norm in {"all", "tables", "summary"}

    buf = io.BytesIO()
    used_names: Set[str] = set()

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary_rows = [
            {"metric": "batch_id", "value": batch.batch_id},
            {"metric": "name", "value": batch.name},
            {"metric": "status", "value": batch.status.value},
            {"metric": "total_tasks", "value": str(batch.total_tasks)},
            {"metric": "completed_tasks", "value": str(batch.completed_tasks)},
            {"metric": "failed_tasks", "value": str(batch.failed_tasks)},
            {"metric": "progress_percent", "value": str(batch.get_progress())},
        ]
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
        used_names.add("Summary")

        if include_kie:
            header, rows = build_kie_csv_rows(batch)
            pd.DataFrame(rows, columns=header).to_excel(writer, sheet_name="KIE", index=False)
            used_names.add("KIE")

        mapped_rows = _collect_mapped_table_rows(batch)
        if mapped_rows:
            pd.DataFrame(mapped_rows).to_excel(writer, sheet_name="MappedRows", index=False)
            used_names.add("MappedRows")

        if include_tables:
            for task in batch.tasks:
                tables = _task_tables(task)
                if not tables:
                    continue
                sheet_base = _sanitize_sheet_name(
                    os.path.splitext(task.file_name)[0],
                    used_names,
                )
                if len(tables) == 1:
                    df = _table_dataframe(tables[0])
                    if not df.empty:
                        df.to_excel(writer, sheet_name=sheet_base, index=False)
                else:
                    for idx, table in enumerate(tables):
                        df = _table_dataframe(table)
                        if df.empty:
                            continue
                        sheet = _sanitize_sheet_name(f"{sheet_base}_T{idx + 1}", used_names)
                        df.to_excel(writer, sheet_name=sheet, index=False)

    return buf.getvalue()


def build_json_bundle(batch: BatchJob) -> Dict[str, Any]:
    tasks_out = []
    for task in batch.tasks:
        entry: Dict[str, Any] = {
            "task_id": task.task_id,
            "file_name": task.file_name,
            "status": task.status.value,
        }
        if task.error:
            entry["error"] = task.error
        if task.result is not None:
            entry["result"] = task.result
        tasks_out.append(entry)
    return {
        "batch_id": batch.batch_id,
        "name": batch.name,
        "status": batch.status.value,
        "options": batch.options,
        "tasks": tasks_out,
    }
