"""Task lifecycle routes: status / events / ws / cancel / kie-fields / delete.

Moved verbatim from main.py (v1.8.2 C2). No ``prefix`` on the APIRouter —
paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.runtime import (
    _apply_kie_fields_to_task,
    task_cancellation_flags,
    task_event_counters,
    task_event_history,
    task_websockets,
    tasks,
)
from app.models.api_models import KieFieldsPatchModel, TaskStatus

router = APIRouter()


@router.get("/api/v1/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatus(**task)


@router.get("/api/v1/tasks/{task_id}/events")
async def get_task_events(task_id: str):
    """Debug endpoint: return stored event history for a task (last 100 events)."""
    events = task_event_history.get(task_id, [])
    return {"events": events}


@router.websocket("/api/v1/tasks/{task_id}/ws")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time task event streaming.
    Connects to a specific task and receives all events in real-time.
    Sends event history to late-connecting clients.
    """
    await websocket.accept()
    logger.info(f"Task {task_id}: WebSocket connection established")

    # Add WebSocket to task's connection set
    if task_id not in task_websockets:
        task_websockets[task_id] = set()
    task_websockets[task_id].add(websocket)

    # Send event history first (for late-connecting clients)
    # Support `since` or `last_event_id` query parameter to only replay events after a given id
    try:
        query = websocket.query_params
        since_val = query.get('since') or query.get('last_event_id') or '0'
        try:
            since_id = int(since_val)
        except Exception:
            since_id = 0
    except Exception:
        since_id = 0

    history = task_event_history.get(task_id, [])
    # Filter history to events with id > since_id
    to_send = [e for e in history if int(e.get('id', 0)) > int(since_id)]
    if to_send:
        logger.info(f"Task {task_id}: Sending {len(to_send)} historical events to new WebSocket connection (since={since_id})")
        max_sent_id = int(since_id)
        for event in to_send:
            try:
                await websocket.send_json(event)
                try:
                    max_sent_id = max(max_sent_id, int(event.get('id', 0)))
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Task {task_id}: Failed to send historical event: {e}")
                break
    else:
        max_sent_id = int(since_id)

    # Send current task status
    task = tasks.get(task_id)
    if task:
        # Build current event and send only if it's newer than any history we just sent
        current_event_id = task_event_counters.get(task_id, 0)
        current_event = {
            "type": "status",
            "status": task.get('status', 'pending'),
            "progress": task.get('progress', 0),
            "message": task.get('message', ''),
            "timestamp": datetime.now().isoformat(),
            "id": current_event_id
        }
        try:
            # If the server already sent history that includes this id, skip sending the duplicate current_event
            if current_event_id > int(max_sent_id):
                await websocket.send_json(current_event)
            else:
                logger.debug(f"Task {task_id}: Skipping current status send (id={current_event_id} <= max_sent_id={max_sent_id})")
        except Exception as e:
            logger.warning(f"Task {task_id}: Failed to send current status: {e}")

    # Handle incoming messages in background task to avoid blocking
    async def handle_messages():
        try:
            while True:
                try:
                    data = await websocket.receive_text()
                    if data == "ping":
                        await websocket.send_text("pong")
                except WebSocketDisconnect:
                    logger.info(f"Task {task_id}: WebSocket disconnected normally")
                    break
                except Exception as e:
                    logger.error(f"Task {task_id}: WebSocket receive error: {e}")
                    break
        except Exception as e:
            logger.error(f"Task {task_id}: Error in message handler: {e}")

    # Start message handler
    message_task = asyncio.create_task(handle_messages())

    try:
        # Wait for message handler to complete (connection closed)
        await message_task
    finally:
        # Clean up: remove WebSocket from task's connection set
        if task_id in task_websockets:
            task_websockets[task_id].discard(websocket)
            if not task_websockets[task_id]:
                task_websockets.pop(task_id, None)
        logger.info(f"Task {task_id}: WebSocket connection closed")


@router.post("/api/v1/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    status = task.get("status")

    if status in ["succeeded", "completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel task with status: {status}")

    # Set cancellation flag
    task_cancellation_flags[task_id] = True
    task["status"] = "cancelled"
    task["message"] = "Task cancelled by user"

    from app.services.persistence.analyze_job_store import persist_task_safe

    await persist_task_safe(task)

    logger.info(f"Task cancelled: {task_id}")
    return {"message": "Task cancelled", "task_id": task_id}


@router.patch("/api/v1/tasks/{task_id}/kie-fields")
async def patch_task_kie_fields(task_id: str, body: KieFieldsPatchModel):
    """Update KIE fields after human review."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    try:
        validation = _apply_kie_fields_to_task(task, body.fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from app.services.persistence.analyze_job_store import persist_task_safe

    await persist_task_safe(task)
    return {
        "task_id": task_id,
        "fields": body.fields,
        "kie_validation": validation,
    }


@router.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task (can delete any task regardless of status)"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]

    # Cancel if still processing
    if task.get("status") in ["pending", "processing"]:
        task_cancellation_flags[task_id] = True
        task["status"] = "cancelled"

    # Clean up files
    upload_dir = os.path.dirname(task.get("file_path", ""))
    if upload_dir and os.path.exists(upload_dir):
        try:
            shutil.rmtree(upload_dir)
        except Exception as e:
            logger.warning(f"Failed to delete upload directory: {e}")

    from app.services.persistence.analyze_job_store import delete_task_safe

    delete_task_safe(task_id)
    tasks.pop(task_id, None)
    task_cancellation_flags.pop(task_id, None)

    return {"message": "Task deleted", "task_id": task_id}
