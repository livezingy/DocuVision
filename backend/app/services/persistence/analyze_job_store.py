"""Single-task analyze-job persistence (v1.7).

Survives ``:8000`` restarts so completed Pro tasks remain queryable
(result / ZIP / figure crops). SQLite stores metadata + a ``result_path``
pointer only; the full result lives on disk as
``OUTPUT_DIR/{task_id}/result.json``.

The in-memory ``tasks`` dict in ``main.py`` stays the runtime cache.
This store binds that dict and hydrates it at startup (no per-request
SQLite lookup). Tests must import this module, not ``app.main``.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from loguru import logger

from app.core.config import settings


class _StoreLike(Protocol):
    def save(self, table: str, key: str, document: dict) -> None: ...

    def load(self, table: str, key: str) -> Optional[dict]: ...

    def load_all(self, table: str) -> List[dict]: ...

    def delete(self, table: str, key: str) -> None: ...


TABLE = "analyze_jobs"

COMPLETED_STATUSES = frozenset({"completed", "succeeded"})
TERMINAL_STATUSES = frozenset(
    {
        "completed",
        "succeeded",
        "failed",
        "cancelled",
        "interrupted",
        "missing_artifacts",
    }
)
BULKY_QUALITY_KEYS = frozenset({"html", "html_structure", "tables"})


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _quality_summary(task: Dict[str, Any]) -> Dict[str, Any]:
    result = task.get("result")
    raw = None
    if isinstance(result, dict):
        raw = result.get("quality")
    if raw is None:
        raw = task.get("quality")
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if k not in BULKY_QUALITY_KEYS}


class AnalyzeJobStore:
    """Persist Pro analyze tasks via ``QueueStore`` + on-disk result.json."""

    TABLE = TABLE

    def __init__(
        self,
        *,
        output_dir: Optional[Path | str] = None,
        keep_last_n: Optional[int] = None,
    ) -> None:
        self._store: Optional[_StoreLike] = None
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._output_dir = Path(output_dir) if output_dir is not None else Path(settings.OUTPUT_DIR)
        if keep_last_n is not None:
            self._keep_last_n = int(keep_last_n)
        else:
            self._keep_last_n = int(getattr(settings, "TASK_KEEP_LAST_N", 50))

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------
    def bind(self, tasks: Dict[str, Dict[str, Any]]) -> None:
        """Use the caller's ``tasks`` dict as the runtime cache."""
        self._tasks = tasks

    def attach_store(self, store: _StoreLike) -> None:
        self._store = store

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    def result_json_path(self, task_id: str) -> Path:
        return self._output_dir / task_id / "result.json"

    def task_output_dir(self, task_id: str) -> Path:
        return self._output_dir / task_id

    # ------------------------------------------------------------------
    # Persist
    # ------------------------------------------------------------------
    def persist_task(self, task: Dict[str, Any]) -> None:
        """Write result.json when completed, then upsert ``analyze_jobs``."""
        if self._store is None:
            return
        task_id = str(task.get("task_id") or "")
        if not task_id:
            logger.warning("analyze_jobs persist skipped: missing task_id")
            return
        status = str(task.get("status") or "")
        result_path: Optional[str] = None
        if status in COMPLETED_STATUSES:
            result_path = self._write_result_json(task_id, task.get("result"))
        row = self._to_row(task, result_path=result_path)
        self._store.save(self.TABLE, task_id, row)
        if status in TERMINAL_STATUSES:
            self.enforce_retention()

    async def persist_task_async(self, task: Dict[str, Any]) -> None:
        if self._store is None:
            return
        await asyncio.to_thread(self.persist_task, task)

    def _persist(self, task: Dict[str, Any]) -> None:
        self.persist_task(task)

    async def _persist_async(self, task: Dict[str, Any]) -> None:
        await self.persist_task_async(task)

    def _write_result_json(self, task_id: str, result: Any) -> Optional[str]:
        if not isinstance(result, dict):
            return None
        path = self.result_json_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return str(path)

    def _to_row(self, task: Dict[str, Any], *, result_path: Optional[str]) -> dict:
        created = _iso(task.get("created_at")) or datetime.now().isoformat()
        return {
            "task_id": str(task.get("task_id") or ""),
            "status": str(task.get("status") or ""),
            "file_name": str(task.get("file_name") or ""),
            "file_path": str(task.get("file_path") or ""),
            "created_at": created,
            "completed_at": _iso(task.get("completed_at")),
            "options": task.get("options") if isinstance(task.get("options"), dict) else {},
            "result_path": result_path,
            "quality": _quality_summary(task),
        }

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    def load_from_db(self) -> int:
        """Rebuild the bound ``tasks`` dict. ``processing`` becomes ``interrupted``."""
        if self._store is None:
            return 0
        rows = self._store.load_all(self.TABLE)
        loaded = 0
        for row in rows:
            try:
                task = self._from_row(row)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("analyze_jobs row skipped ({}): {}", row.get("task_id", "?"), exc)
                continue
            self._tasks[task["task_id"]] = task
            loaded += 1
        logger.info("AnalyzeJobStore loaded {} task(s) from store", loaded)
        return loaded

    def _from_row(self, row: dict) -> Dict[str, Any]:
        task_id = str(row["task_id"])
        status = str(row.get("status") or "")
        result: Any = None
        message = ""

        if status == "processing":
            status = "interrupted"
            message = "Interrupted by server restart; resubmit to retry."

        result_path = row.get("result_path") or ""
        if result_path:
            loaded = self._read_result_json(result_path)
            if loaded is None:
                status = "missing_artifacts"
                result = None
                message = "Result artifacts missing on disk."
            else:
                result = loaded
                if not message and status in COMPLETED_STATUSES:
                    message = "Processing completed"

        options = row.get("options")
        if not isinstance(options, dict):
            options = {}

        quality = row.get("quality")
        if not isinstance(quality, dict):
            quality = {}

        progress = 100 if status in COMPLETED_STATUSES else 0
        return {
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "message": message,
            "created_at": _parse_dt(row.get("created_at")) or row.get("created_at"),
            "completed_at": _parse_dt(row.get("completed_at")),
            "file_path": str(row.get("file_path") or ""),
            "file_name": str(row.get("file_name") or ""),
            "options": options,
            "result": result,
            "quality": quality,
            "result_path": result_path or None,
        }

    def _read_result_json(self, result_path: str) -> Optional[dict]:
        path = Path(result_path)
        if not path.is_file():
            return None
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("analyze_jobs result.json unreadable ({}): {}", path, exc)
            return None
        return loaded if isinstance(loaded, dict) else None

    # ------------------------------------------------------------------
    # Delete / FIFO
    # ------------------------------------------------------------------
    def delete_task(self, task_id: str) -> None:
        """Delete the DB row and ``OUTPUT_DIR/{task_id}/``. Pop the cache."""
        if self._store is not None:
            self._store.delete(self.TABLE, task_id)
        out_dir = self.task_output_dir(task_id)
        if out_dir.is_dir():
            try:
                shutil.rmtree(out_dir)
            except OSError as exc:
                logger.warning("Failed to delete task output dir {}: {}", out_dir, exc)
        self._tasks.pop(task_id, None)

    def enforce_retention(self) -> None:
        """Keep the newest ``TASK_KEEP_LAST_N`` terminal rows; evict row + dir."""
        if self._store is None or self._keep_last_n <= 0:
            return
        rows = self._store.load_all(self.TABLE)
        terminal = [r for r in rows if str(r.get("status") or "") in TERMINAL_STATUSES]
        terminal.sort(key=lambda r: r.get("completed_at") or r.get("created_at") or "", reverse=True)
        for row in terminal[self._keep_last_n :]:
            evict_id = str(row.get("task_id") or "")
            if evict_id:
                self.delete_task(evict_id)


analyze_job_store = AnalyzeJobStore()


async def persist_task_safe(task: Dict[str, Any]) -> None:
    """Persist without failing the caller (SQLite / disk errors are logged)."""
    try:
        await analyze_job_store.persist_task_async(task)
    except Exception as exc:
        logger.warning("Analyze job persist failed (non-fatal): {}", exc)


def delete_task_safe(task_id: str) -> None:
    try:
        analyze_job_store.delete_task(task_id)
    except Exception as exc:
        logger.warning("Analyze job delete failed (non-fatal): {}", exc)
