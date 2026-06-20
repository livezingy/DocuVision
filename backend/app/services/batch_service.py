"""
Batch Processing Service - Queue Management and Parallel Processing
Supports batch document processing with progress tracking
"""

from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import uuid
import os
from loguru import logger


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
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


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


class BatchService:
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
        on_progress: Callable[[str, str, float, str], None] = None
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
        
        max_conc = self._effective_concurrency(batch)
        task = asyncio.create_task(
            self._process_batch(batch_id, process_func, on_progress, max_concurrent=max_conc)
        )
        self._active_batches[batch_id] = task
        
        logger.info(f"Started batch processing: {batch_id}")
        return True
    
    async def _process_batch(
        self,
        batch_id: str,
        process_func: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]],
        on_progress: Callable[[str, str, float, str], None] = None,
        max_concurrent: Optional[int] = None,
    ):
        """Internal batch processing logic"""
        batch = self.batches.get(batch_id)
        if not batch:
            return
        
        try:
            limit = max_concurrent if max_concurrent is not None else self.max_concurrent
            semaphore = asyncio.Semaphore(max(1, limit))
            
            async def process_task(task: BatchTask):
                # Check for cancellation or pause
                if batch_id in self._cancelled_batches:
                    task.status = TaskStatus.SKIPPED
                    return
                
                while batch_id in self._paused_batches:
                    await asyncio.sleep(1)
                    if batch_id in self._cancelled_batches:
                        task.status = TaskStatus.SKIPPED
                        return
                
                async with semaphore:
                    task.status = TaskStatus.PROCESSING
                    task.started_at = datetime.now()
                    task.message = "Processing..."
                    
                    if on_progress:
                        on_progress(batch_id, task.task_id, 0, "Processing...")
                    
                    try:
                        # Process the file
                        result = await process_func(task.file_path, batch.options)
                        
                        task.status = TaskStatus.COMPLETED
                        task.progress = 100.0
                        task.result = result
                        task.message = "Completed"
                        task.completed_at = datetime.now()
                        
                        batch.completed_tasks += 1
                        
                        if on_progress:
                            on_progress(batch_id, task.task_id, 100, "Completed")
                        
                    except Exception as e:
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        task.message = f"Failed: {str(e)}"
                        task.completed_at = datetime.now()
                        
                        batch.failed_tasks += 1
                        
                        if on_progress:
                            on_progress(batch_id, task.task_id, 0, f"Failed: {str(e)}")
                        
                        logger.error(f"Task {task.task_id} failed: {e}")
            
            # Process all tasks concurrently
            pending_tasks = [t for t in batch.tasks if t.status == TaskStatus.PENDING]
            await asyncio.gather(*[process_task(task) for task in pending_tasks])
            
            # Check final status
            if batch_id in self._cancelled_batches:
                batch.status = BatchStatus.CANCELLED
            elif batch.failed_tasks == batch.total_tasks:
                batch.status = BatchStatus.FAILED
            else:
                batch.status = BatchStatus.COMPLETED
            
            batch.completed_at = datetime.now()
            
            logger.info(f"Batch {batch_id} finished: {batch.completed_tasks}/{batch.total_tasks} completed, {batch.failed_tasks} failed")

            try:
                from app.services.webhook_service import webhook_registry

                asyncio.create_task(
                    webhook_registry.dispatch_event_async(
                        "batch.completed",
                        {
                            "batch_id": batch_id,
                            "name": batch.name,
                            "status": batch.status.value,
                            "completed_tasks": batch.completed_tasks,
                            "failed_tasks": batch.failed_tasks,
                        },
                    )
                )
            except Exception as hook_exc:
                logger.debug(f"Batch webhook dispatch skipped: {hook_exc}")
            
        except Exception as e:
            batch.status = BatchStatus.FAILED
            batch.completed_at = datetime.now()
            logger.error(f"Batch {batch_id} failed: {e}")
        
        finally:
            # Clean up
            self._active_batches.pop(batch_id, None)
    
    async def pause_batch(self, batch_id: str) -> bool:
        """Pause a running batch"""
        batch = self.batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        if batch.status != BatchStatus.PROCESSING:
            return False
        
        self._paused_batches.add(batch_id)
        batch.status = BatchStatus.PAUSED
        logger.info(f"Paused batch: {batch_id}")
        return True
    
    async def resume_batch(
        self,
        batch_id: str,
        process_func: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]] = None,
        on_progress: Callable[[str, str, float, str], None] = None
    ) -> bool:
        """Resume a paused batch"""
        batch = self.batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        if batch.status != BatchStatus.PAUSED:
            return False
        
        self._paused_batches.discard(batch_id)
        batch.status = BatchStatus.PROCESSING
        pending = [t for t in batch.tasks if t.status == TaskStatus.PENDING]
        if process_func is not None and pending and batch_id not in self._active_batches:
            max_conc = self._effective_concurrency(batch)
            task = asyncio.create_task(
                self._process_batch(batch_id, process_func, on_progress, max_concurrent=max_conc)
            )
            self._active_batches[batch_id] = task
        logger.info(f"Resumed batch: {batch_id}")
        return True
    
    async def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a batch job"""
        batch = self.batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        if batch.status in [BatchStatus.COMPLETED, BatchStatus.CANCELLED]:
            return False
        
        self._cancelled_batches.add(batch_id)
        self._paused_batches.discard(batch_id)
        
        # Wait for active task to finish
        if batch_id in self._active_batches:
            task = self._active_batches[batch_id]
            # Give it some time to gracefully finish
            await asyncio.sleep(0.5)
        
        batch.status = BatchStatus.CANCELLED
        batch.completed_at = datetime.now()
        
        # Mark remaining pending tasks as skipped
        for task in batch.tasks:
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.SKIPPED
        
        logger.info(f"Cancelled batch: {batch_id}")
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
        
        logger.info(f"Reset {retried} failed tasks in batch {batch_id}")
        return retried

