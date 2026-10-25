"""Batch runner mixin — the in-flight batch processing state machine.

Split from the former batch_service.py monolith (S1 batch 8): `_process_batch`
plus pause/resume/cancel run control, operating on the shared instance state
(``batches`` / ``_active_batches`` / ``_cancelled_batches`` /
``_paused_batches``) owned by the facade's ``__init__`` — hence a mixin, not
free functions. The former inline webhook dispatch became the injected
``on_complete`` callback (routers/batch.py injects the webhook closure; the
services-layer batch->infra frozen edge dissolves).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from loguru import logger

from app.services.batch_models import BatchStatus, BatchTask, TaskStatus


class BatchRunnerMixin:
    """Run control for batch jobs (process loop, pause/resume/cancel)."""

    def _notify_batch_complete(
        self,
        batch_id: str,
        on_complete: Optional[Callable[[Dict[str, Any]], Awaitable[None]]],
    ) -> None:
        """Fire the batch-completion callback fire-and-forget.

        Callback scheduling failures are swallowed to a debug log so dispatch
issues can never affect batch final state (same semantics the inline
webhook block had before the batch 8 dissolution).
        """
        if on_complete is None:
            return
        batch = self.batches.get(batch_id)
        if batch is None:
            return
        try:
            asyncio.create_task(
                on_complete(
                    {
                        "batch_id": batch_id,
                        "name": batch.name,
                        "status": batch.status.value,
                        "completed_tasks": batch.completed_tasks,
                        "failed_tasks": batch.failed_tasks,
                    }
                )
            )
        except Exception as hook_exc:
            logger.debug(f"Batch completion callback skipped: {hook_exc}")


    async def _process_batch(
        self,
        batch_id: str,
        process_func: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]],
        on_progress: Callable[[str, str, float, str], None] = None,
        max_concurrent: Optional[int] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
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
                        await self._persist_async(batch)

                        if on_progress:
                            on_progress(batch_id, task.task_id, 100, "Completed")

                    except Exception as e:
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        task.message = f"Failed: {str(e)}"
                        task.completed_at = datetime.now()

                        batch.failed_tasks += 1
                        await self._persist_async(batch)

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
            await self._persist_async(batch)

            logger.info(f"Batch {batch_id} finished: {batch.completed_tasks}/{batch.total_tasks} completed, {batch.failed_tasks} failed")
            self._notify_batch_complete(batch_id, on_complete)
            
        except Exception as e:
            batch.status = BatchStatus.FAILED
            batch.completed_at = datetime.now()
            await self._persist_async(batch)
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
        await self._persist_async(batch)
        logger.info(f"Paused batch: {batch_id}")
        return True

    async def resume_batch(
        self,
        batch_id: str,
        process_func: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]] = None,
        on_progress: Callable[[str, str, float, str], None] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
    ) -> bool:
        """Resume a paused batch"""
        batch = self.batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        if batch.status != BatchStatus.PAUSED:
            return False
        
        self._paused_batches.discard(batch_id)
        pending = [t for t in batch.tasks if t.status == TaskStatus.PENDING]
        if not pending:
            # Nothing to resume (e.g. crash happened after all tasks finished
            # but before the batch-level final status flip). Finalize now
            # instead of leaving the batch stuck in PROCESSING.
            if batch_id in self._cancelled_batches:
                batch.status = BatchStatus.CANCELLED
            elif batch.failed_tasks == batch.total_tasks:
                batch.status = BatchStatus.FAILED
            else:
                batch.status = BatchStatus.COMPLETED
            batch.completed_at = datetime.now()
            await self._persist_async(batch)
            logger.info(
                f"Resumed batch {batch_id} with no pending tasks; finalized as {batch.status.value}"
            )
            return True
        batch.status = BatchStatus.PROCESSING
        await self._persist_async(batch)
        if process_func is not None and batch_id not in self._active_batches:
            max_conc = self._effective_concurrency(batch)
            task = asyncio.create_task(
                self._process_batch(batch_id, process_func, on_progress, max_concurrent=max_conc, on_complete=on_complete)
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

        await self._persist_async(batch)
        logger.info(f"Cancelled batch: {batch_id}")
        return True
