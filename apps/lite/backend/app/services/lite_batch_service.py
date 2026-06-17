"""In-memory Lite batch jobs (table-only ETL)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from app.services.table_pipeline import extract_tables_from_pdf
from app.schemas.lite_result import ExtractMode


class LiteBatchStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LiteTaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class LiteBatchTask:
    task_id: str
    file_path: str
    file_name: str
    status: LiteTaskStatus = LiteTaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class LiteBatchJob:
    batch_id: str
    name: str
    tasks: List[LiteBatchTask] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)
    status: LiteBatchStatus = LiteBatchStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "name": self.name,
            "status": self.status.value,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "options": self.options,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "file_name": t.file_name,
                    "status": t.status.value,
                    "error": t.error,
                }
                for t in self.tasks
            ],
        }

    def get_progress(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return round(100.0 * (self.completed_tasks + self.failed_tasks) / self.total_tasks, 1)


class LiteBatchService:
    def __init__(self) -> None:
        self.batches: Dict[str, LiteBatchJob] = {}

    def create_batch(self, name: str, files: List[Dict[str, str]], options: Optional[Dict[str, Any]] = None) -> LiteBatchJob:
        batch_id = str(uuid.uuid4())
        tasks = [
            LiteBatchTask(task_id=str(uuid.uuid4()), file_path=f["file_path"], file_name=f["file_name"])
            for f in files
        ]
        batch = LiteBatchJob(
            batch_id=batch_id,
            name=name,
            tasks=tasks,
            options=options or {"table_only": True},
            total_tasks=len(tasks),
        )
        self.batches[batch_id] = batch
        return batch

    def get_batch(self, batch_id: str) -> Optional[LiteBatchJob]:
        return self.batches.get(batch_id)

    async def start_batch(self, batch_id: str) -> None:
        batch = self.get_batch(batch_id)
        if not batch:
            raise ValueError("Batch not found")
        batch.status = LiteBatchStatus.PROCESSING
        for task in batch.tasks:
            if task.status != LiteTaskStatus.PENDING:
                continue
            task.status = LiteTaskStatus.PROCESSING
            try:
                output = extract_tables_from_pdf(
                    Path(task.file_path),
                    mode=ExtractMode.SMART,
                    engine="auto",
                    flavor="auto",
                )
                task.result = output
                task.status = LiteTaskStatus.COMPLETED
                batch.completed_tasks += 1
            except Exception as exc:
                task.status = LiteTaskStatus.FAILED
                task.error = str(exc)
                batch.failed_tasks += 1
                logger.warning(f"Lite batch task failed: {exc}")
        batch.status = LiteBatchStatus.COMPLETED if batch.failed_tasks == 0 else LiteBatchStatus.FAILED


lite_batch_service = LiteBatchService()
