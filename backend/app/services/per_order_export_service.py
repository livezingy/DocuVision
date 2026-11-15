"""Per-order CSV split export (R-003/P-042 T5, AC6).

Batch-level ``per_order=True`` opt-in: every completed task of the batch that
produced mapping rows (``mapped_table_rows``, T2 stamp honored) gets its own
CSV file — "one CSV file per order in a set format" (R-003 demand anchor) —
written into a configurable directory with ERP watch semantics: the ERP
watches the directory and consumes whatever order files land there.

File-level idempotency (AC6): filenames are derived deterministically from the
order (sanitized file stem; duplicate stems get a stable ``_<task_id[:8]>``
suffix), so a batch re-run (``retry_failed_tasks`` -> resume ->
``batch.completed`` fires again) overwrites the exact same paths and never
duplicates files.

Content: the task's mapping-result rows in the same columns as the aggregate
MappedRows face (``batch_export_service._mapped_rows_columns``, same-domain
family reuse) rendered through ``batch_export_service.render_csv`` — every
order file carries the identical header set, so ERP column mapping stays
stable across orders. Completed tasks without mapping rows are skipped (no
empty CSVs for the ERP to trip on); failures propagate to the caller — the
routers-layer ``on_complete`` closure swallows them (never affects batch
final state, same contract as webhook/Sheets dispatch).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services.batch_service import BatchJob, BatchTask, TaskStatus

__all__ = ["build_order_csv", "export_batch_per_order"]

_UNSAFE_FILENAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_MAX_STEM_LEN = 100


def _task_mapped_rows(task: BatchTask) -> List[Dict[str, Any]]:
    """The task's mapping-result rows with file_name attached (same shape as
    the aggregate MappedRows face rows)."""
    if task.status != TaskStatus.COMPLETED or not isinstance(task.result, dict):
        return []
    mapped = task.result.get("mapped_table_rows")
    if not isinstance(mapped, list):
        return []
    rows: List[Dict[str, Any]] = []
    for entry in mapped:
        if isinstance(entry, dict):
            row = dict(entry)
            row["file_name"] = task.file_name
            rows.append(row)
    return rows


def build_order_csv(
    batch: BatchJob,
    task: BatchTask,
) -> Optional[Tuple[List[str], List[Dict[str, Any]]]]:
    """(header, rows) for one order — the task's mapping rows in the
    aggregate face's columns (mapping-result-driven: the ``mapped_table_fields``
    stamp wins, legacy first-seen order otherwise). ``None`` when the task
    produced no mapping rows."""
    rows = _task_mapped_rows(task)
    if not rows:
        return None
    # same-domain family reuse (batch): identical column derivation as the
    # aggregate MappedRows face so every per-order file shares one format.
    from app.services.batch_export_service import _mapped_rows_columns

    header = _mapped_rows_columns(batch, rows)
    return header, rows


def _order_stem(task: BatchTask) -> str:
    base = os.path.basename(str(task.file_name or "").strip())
    stem = _UNSAFE_FILENAME_RE.sub("_", str(Path(base).stem)).strip().strip(".").strip()
    return (stem or "order")[:_MAX_STEM_LEN]


def _order_filenames(batch: BatchJob) -> Dict[str, str]:
    """task_id -> deterministic CSV filename; duplicate stems (two tasks
    carrying the same file_name) get a stable task-id suffix. The suffix
    prefix width grows until the names are unique (task ids are unique within
    a batch, so this terminates) — re-runs compute the exact same names
    (file-level idempotency)."""
    stems = {task.task_id: _order_stem(task) for task in batch.tasks}
    counts: Dict[str, int] = {}
    for stem in stems.values():
        counts[stem] = counts.get(stem, 0) + 1
    names: Dict[str, str] = {}
    colliding: List[str] = []
    for task in batch.tasks:
        if counts[stems[task.task_id]] > 1:
            colliding.append(task.task_id)
            continue
        names[task.task_id] = f"{stems[task.task_id]}.csv"

    keys: Dict[str, str] = {}
    width = 8
    max_width = max((len(str(tid)) for tid in colliding), default=width)
    while width <= max_width:
        keys = {
            tid: f"{stems[tid][: max(_MAX_STEM_LEN - width - 1, 1)]}_{str(tid)[:width]}"
            for tid in colliding
        }
        if len(set(keys.values())) == len(keys):
            break
        width += 1
    if not keys:
        return names
    if len(set(keys.values())) != len(keys):
        # unreachable while task ids are unique within a batch — fail closed
        raise ValueError("per-order export failed: cannot disambiguate order filenames")
    for tid in colliding:
        names[tid] = f"{keys[tid]}.csv"
    return names


def export_batch_per_order(batch: BatchJob, output_dir: str) -> Dict[str, Any]:
    """Write one CSV per order (completed task with mapping rows) into
    ``output_dir`` via ``render_csv``; re-runs overwrite the same
    deterministic paths — no duplicate files. Batches without mapping rows
    write nothing. Returns a summary dict (paths, row counts, skipped
    tasks); write failures propagate (the router closure swallows them)."""
    from app.services.batch_export_service import render_csv

    target_dir = str(output_dir or "").strip()
    if not target_dir:
        raise ValueError("per-order export failed: no output directory configured")

    filenames = _order_filenames(batch)
    orders: List[Tuple[BatchTask, List[str], List[Dict[str, Any]]]] = []
    skipped: List[str] = []
    for task in batch.tasks:
        order_csv = build_order_csv(batch, task)
        if order_csv is None:
            skipped.append(task.task_id)
            continue
        orders.append((task, order_csv[0], order_csv[1]))

    if not orders:
        return {
            "output_dir": target_dir,
            "written": 0,
            "orders": [],
            "skipped_tasks": skipped,
        }

    os.makedirs(target_dir, exist_ok=True)
    written: List[Dict[str, Any]] = []
    for task, header, rows in orders:
        path = os.path.join(target_dir, filenames[task.task_id])
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(render_csv(header, rows))
        written.append(
            {
                "task_id": task.task_id,
                "file_name": task.file_name,
                "order_file": path,
                "rows": len(rows),
            }
        )
    return {
        "output_dir": target_dir,
        "written": len(written),
        "orders": written,
        "skipped_tasks": skipped,
    }
