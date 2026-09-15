"""Job routes: GET /api/v1/jobs/{job_id}[/result|/debug|/debug/{filename}].

Moved verbatim from main.py (v1.8.2 C1e). No ``prefix`` on the APIRouter —
paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.runtime import tasks
from app.models.api_models import JobEnvelope, JobStatus

router = APIRouter()


@router.get("/api/v1/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """
    Phase 1 API: Get current job status and progress.
    """
    task = tasks.get(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatus(
        job_id=job_id,
        status=task.get("status"),
        progress=task.get("progress", 0),
        message=task.get("message", ""),
        created_at=task.get("created_at"),
        completed_at=task.get("completed_at"),
    )


@router.get("/api/v1/jobs/{job_id}/result", response_model=JobEnvelope, response_model_exclude_none=True)
async def get_job_result(job_id: str):
    """
    Phase 1 API: Get the completed Envelope result.
    Returns 404 if job not found or not completed.
    Returns JobEnvelope with preprocessing, raw, fused, view, quality layers.
    """
    task = tasks.get(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    if task.get("status") not in ("succeeded", "completed"):
        raise HTTPException(
            status_code=409,
            detail=f"Job not completed. Current status: {task.get('status')}"
        )

    envelope_dict = task.get("envelope")
    if not envelope_dict:
        raise HTTPException(
            status_code=500,
            detail="Job result envelope not found"
        )

    if not bool(task.get("options", {}).get("return_raw", False)):
        envelope_dict = dict(envelope_dict)
        envelope_dict["raw"] = {}

    # Convert dict to JobEnvelope model
    return JobEnvelope(**envelope_dict)


@router.get("/api/v1/jobs/{job_id}/debug")
async def get_job_debug(job_id: str):
    """
    Phase 1 API: Get debug artifacts (preprocessing, raw, fused, quality JSON + images).

    Returns 404 if:
    - Job not found
    - DEBUG_MODE is disabled
    - Job not completed

    Returns a manifest with debug artifact paths and metadata.
    """
    if not settings.DEBUG_MODE:
        raise HTTPException(
            status_code=404,
            detail="Debug mode is disabled"
        )

    task = tasks.get(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    if task.get("status") != "succeeded":
        raise HTTPException(
            status_code=409,
            detail=f"Job not completed. Current status: {task.get('status')}"
        )

    debug_dir = os.path.join(settings.DEBUG_OUTPUT_DIR, job_id)
    if not os.path.exists(debug_dir):
        raise HTTPException(
            status_code=404,
            detail="Debug artifacts not found"
        )

    # List debug files
    debug_files = []
    for filename in os.listdir(debug_dir):
        filepath = os.path.join(debug_dir, filename)
        if os.path.isfile(filepath):
            debug_files.append({
                "filename": filename,
                "path": f"/api/v1/jobs/{job_id}/debug/{filename}",
                "size": os.path.getsize(filepath),
            })

    return {
        "job_id": job_id,
        "debug_dir": debug_dir,
        "artifacts": debug_files,
    }


@router.get("/api/v1/jobs/{job_id}/debug/{filename}")
async def get_job_debug_file(job_id: str, filename: str):
    """
    Phase 1 API: Download a specific debug artifact file.
    """
    if not settings.DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Debug mode is disabled")

    task = tasks.get(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    filepath = os.path.join(settings.DEBUG_OUTPUT_DIR, job_id, filename)

    # Security: prevent directory traversal (use resolved path containment,
    # not startswith, to reject sibling dirs like ./debug2/...)
    base_dir = Path(settings.DEBUG_OUTPUT_DIR).resolve()
    try:
        resolved = Path(filepath).resolve()
        if not resolved.is_relative_to(base_dir):
            raise HTTPException(status_code=403, detail="Access denied")
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(filepath)
