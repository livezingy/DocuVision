"""Batch data models — enums, dataclasses and their serialization round-trip.

Split from the former batch_service.py monolith (S1 batch 8); pure data with
no asyncio and no service imports. Re-exported by the batch_service facade
for the existing import sites (routers/batch, batch_export_service, tests).
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Protocol
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class _StoreLike(Protocol):
    def save(self, table: str, key: str, document: dict) -> None: ...
    def load_all(self, table: str) -> List[dict]: ...
    def delete(self, table: str, key: str) -> None: ...


class BatchStatus(str, Enum):
    """Batch job status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskStatus(str, Enum):
    """Individual task status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class BatchTask:
    """Individual task in a batch"""
    task_id: str
    file_path: str
    file_name: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "status": self.status.value if isinstance(self.status, TaskStatus) else str(self.status),
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BatchTask":
        def _parse_dt(v: Any) -> Optional[datetime]:
            if not v:
                return None
            if isinstance(v, datetime):
                return v
            try:
                return datetime.fromisoformat(str(v))
            except (ValueError, TypeError):
                return None

        raw_status = d.get("status", TaskStatus.PENDING.value)
        try:
            status = TaskStatus(raw_status) if isinstance(raw_status, str) else raw_status
        except ValueError:
            status = TaskStatus.PENDING
        return cls(
            task_id=str(d["task_id"]),
            file_path=str(d.get("file_path", "")),
            file_name=str(d.get("file_name", "")),
            status=status,
            progress=float(d.get("progress", 0.0) or 0.0),
            message=str(d.get("message", "")),
            result=d.get("result"),
            error=d.get("error"),
            started_at=_parse_dt(d.get("started_at")),
            completed_at=_parse_dt(d.get("completed_at")),
        )


@dataclass
class BatchJob:
    """Batch processing job"""
    batch_id: str
    name: str
    status: BatchStatus = BatchStatus.PENDING
    tasks: List[BatchTask] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "name": self.name,
            "status": self.status.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "options": self.options,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "progress": self.get_progress()
        }
    
    def get_progress(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return round((self.completed_tasks + self.failed_tasks) / self.total_tasks * 100, 2)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BatchJob":
        def _parse_dt(v: Any) -> Optional[datetime]:
            if not v:
                return None
            if isinstance(v, datetime):
                return v
            try:
                return datetime.fromisoformat(str(v))
            except (ValueError, TypeError):
                return None

        raw_status = d.get("status", BatchStatus.PENDING.value)
        try:
            status = BatchStatus(raw_status) if isinstance(raw_status, str) else raw_status
        except ValueError:
            status = BatchStatus.PENDING

        raw_tasks = d.get("tasks", [])
        if isinstance(raw_tasks, str):
            import json as _json
            try:
                raw_tasks = _json.loads(raw_tasks)
            except (ValueError, TypeError):
                raw_tasks = []
        tasks = [BatchTask.from_dict(t) for t in raw_tasks if isinstance(t, dict)]

        raw_options = d.get("options", {})
        if isinstance(raw_options, str):
            import json as _json
            try:
                raw_options = _json.loads(raw_options)
            except (ValueError, TypeError):
                raw_options = {}
        if not isinstance(raw_options, dict):
            raw_options = {}

        return cls(
            batch_id=str(d["batch_id"]),
            name=str(d.get("name", "")),
            status=status,
            tasks=tasks,
            options=raw_options,
            created_at=_parse_dt(d.get("created_at")) or datetime.now(),
            started_at=_parse_dt(d.get("started_at")),
            completed_at=_parse_dt(d.get("completed_at")),
            total_tasks=int(d.get("total_tasks", 0) or 0),
            completed_tasks=int(d.get("completed_tasks", 0) or 0),
            failed_tasks=int(d.get("failed_tasks", 0) or 0),
        )
