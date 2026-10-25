"""Batch Processing Service facade - queue management and parallel processing.

Keeps ``BatchService`` (store wiring, CRUD, queries, ``start_batch`` entry)
and composes the run-control mixin; the data models live in
``batch_models.py`` and the processing loop in ``batch_runner.py`` (S1 batch 8
split of the former monolith). The webhook completion dispatch is injected as
an ``on_complete`` callback by ``routers/batch.py``.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from loguru import logger

from app.services.batch_models import (  # noqa: F401 (re-export; consumers import the type names from here)
    BatchJob,
    BatchStatus,
    BatchTask,
    TaskStatus,
    _StoreLike,
)
from app.services.batch_runner import BatchRunnerMixin


class BatchService(BatchRunnerMixin):
    """
    Batch Processing Service
    
    Features:
    - Create batch jobs with multiple files
    - Parallel processing with configurable concurrency
    - Progress tracking and status updates
    - Pause/Resume/Cancel operations
    - Result aggregation
    """
    def __init__(self, max_concurrent: int = 3):
        self.batches: Dict[str, BatchJob] = {}
        self.max_concurrent = max_concurrent
        self._processing_lock = asyncio.Lock()
        self._active_batches: Dict[str, asyncio.Task] = {}
        self._cancelled_batches: set = set()
        self._paused_batches: set = set()
        self._store: Optional[_StoreLike] = None

    TABLE = "batch_jobs"

    # ------------------------------------------------------------------
    # Store wiring
    # ------------------------------------------------------------------
    def attach_store(self, store: _StoreLike) -> None:
        """Attach a ``QueueStore`` for crash/restart recovery."""
        self._store = store

    def load_from_db(self) -> int:
        """Rebuild ``self.batches`` from the store.

        - ``processing`` batches are demoted to ``paused`` (no auto GPU resume).
        - ``processing`` tasks are demoted to ``pending`` so they can be retried
          on a manual ``resume_batch``.
        - Runtime-only state (``_active_batches``/``_cancelled``/``_paused``) is
          cleared; it is not persisted.
        """
        if self._store is None:
            return 0
        rows = self._store.load_all(self.TABLE)
        loaded = 0
        for row in rows:
            try:
                batch = BatchJob.from_dict(row)
            except (KeyError, ValueError) as exc:
                logger.warning("batch_jobs row skipped ({}): {}", row.get("batch_id", "?"), exc)
                continue
            if batch.status == BatchStatus.PROCESSING:
                batch.status = BatchStatus.PAUSED
                for task in batch.tasks:
                    if task.status == TaskStatus.PROCESSING:
                        task.status = TaskStatus.PENDING
            self.batches[batch.batch_id] = batch
            loaded += 1
        self._active_batches.clear()
        self._cancelled_batches.clear()
        self._paused_batches.clear()
        logger.info("BatchService loaded {} batch(es) from store", loaded)
        return loaded

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _persist(self, batch: BatchJob) -> None:
        if self._store is None:
            return
        self._store.save(self.TABLE, batch.batch_id, batch.to_dict())

    async def _persist_async(self, batch: BatchJob) -> None:
        if self._store is None:
            return
        await asyncio.to_thread(self._persist, batch)

    def create_batch(
        self,
        name: str,
        files: List[Dict[str, Any]],
        options: Dict[str, Any] = None
    ) -> BatchJob:
        """
        Create a new batch job
        
        Args:
            name: Batch job name
            files: List of files with file_path and file_name
            options: Processing options for all files
        
        Returns:
            Created BatchJob
        """
        batch_id = str(uuid.uuid4())
        
        tasks = []
        for file_info in files:
            task = BatchTask(
                task_id=str(uuid.uuid4()),
                file_path=file_info["file_path"],
                file_name=file_info["file_name"]
            )
            tasks.append(task)
        
        batch = BatchJob(
            batch_id=batch_id,
            name=name,
            tasks=tasks,
            options=options or {},
            total_tasks=len(tasks)
        )
        
        self.batches[batch_id] = batch
        self._persist(batch)
        logger.info(f"Created batch job: {batch_id} with {len(tasks)} tasks")

        return batch

    def get_batch(self, batch_id: str) -> Optional[BatchJob]:
        """Get batch job by ID"""
        return self.batches.get(batch_id)

    def list_batches(
        self,
        status: BatchStatus = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List batch jobs with optional filtering"""
        batches = list(self.batches.values())
        
        if status:
            batches = [b for b in batches if b.status == status]
        
        # Sort by created_at descending
        batches.sort(key=lambda b: b.created_at, reverse=True)
        
        # Apply pagination
        batches = batches[offset:offset + limit]
        
        return [b.to_dict() for b in batches]

    def _effective_concurrency(self, batch: BatchJob) -> int:
        if batch.options.get("enable_kie"):
            from app.core.config import settings
            return max(1, int(settings.BATCH_MAX_CONCURRENT_KIE))
        return self.max_concurrent

    async def start_batch(
        self,
        batch_id: str,
        process_func: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]],
        on_progress: Callable[[str, str, float, str], None] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
    ) -> bool:
        """
        Start processing a batch job
        
        Args:
            batch_id: Batch job ID
            process_func: Async function to process each file
            on_progress: Callback for progress updates (batch_id, task_id, progress, message)
        
        Returns:
            True if started successfully
        """
        batch = self.batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        if batch.status == BatchStatus.PROCESSING:
            raise ValueError("Batch is already processing")
        
        if batch.status == BatchStatus.COMPLETED:
            raise ValueError("Batch is already completed")
        
        # Remove from cancelled/paused sets if present
        self._cancelled_batches.discard(batch_id)
        self._paused_batches.discard(batch_id)
        
        # Update status
        batch.status = BatchStatus.PROCESSING
        batch.started_at = datetime.now()
        await self._persist_async(batch)

        max_conc = self._effective_concurrency(batch)
        task = asyncio.create_task(
            self._process_batch(batch_id, process_func, on_progress, max_concurrent=max_conc, on_complete=on_complete)
        )
        self._active_batches[batch_id] = task

        logger.info(f"Started batch processing: {batch_id}")
        return True

    def delete_batch(self, batch_id: str) -> bool:
        """Delete a batch job"""
        if batch_id not in self.batches:
            return False
        
        batch = self.batches[batch_id]
        
        # Can't delete processing batch
        if batch.status == BatchStatus.PROCESSING:
            raise ValueError("Cannot delete a processing batch. Cancel it first.")
        
        del self.batches[batch_id]
        self._cancelled_batches.discard(batch_id)
        self._paused_batches.discard(batch_id)

        if self._store is not None:
            try:
                self._store.delete(self.TABLE, batch_id)
            except Exception as exc:
                logger.warning(f"Failed to delete batch {batch_id} from store: {exc}")

        logger.info(f"Deleted batch: {batch_id}")
        return True

    def get_batch_summary(self, batch_id: str) -> Dict[str, Any]:
        """Get summary statistics for a batch"""
        batch = self.batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        # Calculate statistics
        status_counts = {}
        for task in batch.tasks:
            status = task.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Calculate processing time
        processing_time = None
        if batch.started_at:
            end_time = batch.completed_at or datetime.now()
            processing_time = (end_time - batch.started_at).total_seconds()
        
        # Calculate success rate
        total_processed = batch.completed_tasks + batch.failed_tasks
        success_rate = (batch.completed_tasks / total_processed * 100) if total_processed > 0 else 0
        
        return {
            "batch_id": batch_id,
            "name": batch.name,
            "status": batch.status.value,
            "total_tasks": batch.total_tasks,
            "status_counts": status_counts,
            "progress": batch.get_progress(),
            "success_rate": round(success_rate, 2),
            "processing_time_seconds": processing_time,
            "created_at": batch.created_at.isoformat(),
            "started_at": batch.started_at.isoformat() if batch.started_at else None,
            "completed_at": batch.completed_at.isoformat() if batch.completed_at else None
        }

    def get_batch_results(self, batch_id: str) -> List[Dict[str, Any]]:
        """Get all results from a batch"""
        batch = self.batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        results = []
        for task in batch.tasks:
            results.append({
                "task_id": task.task_id,
                "file_name": task.file_name,
                "status": task.status.value,
                "result": task.result,
                "error": task.error
            })
        
        return results

    def retry_failed_tasks(self, batch_id: str) -> int:
        """Reset failed tasks to pending for retry"""
        batch = self.batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        if batch.status == BatchStatus.PROCESSING:
            raise ValueError("Cannot retry while batch is processing")
        
        retried = 0
        for task in batch.tasks:
            if task.status == TaskStatus.FAILED:
                task.status = TaskStatus.PENDING
                task.error = None
                task.result = None
                task.progress = 0
                task.message = ""
                task.started_at = None
                task.completed_at = None
                retried += 1
        
        if retried > 0:
            batch.failed_tasks -= retried
            batch.status = BatchStatus.PENDING
            batch.completed_at = None
            self._persist(batch)

        logger.info(f"Reset {retried} failed tasks in batch {batch_id}")
        return retried

