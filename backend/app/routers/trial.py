"""Trial routes: POST /api/v1/trial/gt-diff/{task_id} and its report.

Moved verbatim from main.py (v1.8.2 C2). No ``prefix`` on the APIRouter —
paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.runtime import tasks
from app.models.api_models import TrialGtDiffModel

router = APIRouter()


@router.post("/api/v1/trial/gt-diff/{task_id}")
async def trial_gt_diff(task_id: str, body: TrialGtDiffModel):
    """Run a ground-truth diff against a completed task (GLM trial P1-4).

    The client (or operator) supplies expected values; the endpoint returns
    a field/cell-level accuracy report and persists a self-contained HTML
    report served at GET /api/v1/trial/gt-diff/{task_id}/report.
    """
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") not in ("succeeded", "completed"):
        raise HTTPException(status_code=400, detail="Task not completed yet")

    from app.services.trial.gt_diff import run_diff

    report_dir = os.path.join(settings.OUTPUT_DIR, task_id)
    html_path = os.path.join(report_dir, "gt_diff_report.html")
    report = run_diff(
        body.model_dump(),
        task.get("result") or {},
        job_id=task_id,
        output_html_path=html_path,
        case_sensitive=body.case_sensitive,
    )
    report["report_url"] = f"/api/v1/trial/gt-diff/{task_id}/report"
    return report


@router.get("/api/v1/trial/gt-diff/{task_id}/report")
async def trial_gt_diff_report_file(task_id: str):
    """Serve the generated HTML accuracy report (GLM trial P1-4)."""
    import re as _re

    if not _re.fullmatch(r"[A-Za-z0-9_\-]+", task_id or ""):
        raise HTTPException(status_code=400, detail="Invalid task id")
    path = os.path.join(settings.OUTPUT_DIR, task_id, "gt_diff_report.html")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Report not generated yet")
    return FileResponse(path, media_type="text/html")
