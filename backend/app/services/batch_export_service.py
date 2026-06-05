"""Aggregate batch task results into CSV / JSON exports."""

from __future__ import annotations

import csv
import io
import json
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
