"""Lite job and export routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.schemas.lite_result import JobStatus, LiteError, LiteErrorResponse, LiteJobStatus, LiteResult
from app.services.job_store import job_store
from docuvision_core.export.tables import export_tables_to_csv, export_tables_to_xlsx

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=LiteJobStatus)
def get_job(job_id: str) -> LiteJobStatus:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=LiteErrorResponse(error=LiteError(code="job_not_found", message=f"Job not found: {job_id}")).model_dump(),
        )
    return LiteJobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        created_at=job.get("created_at"),
        updated_at=job.get("updated_at"),
    )


@router.get("/jobs/{job_id}/result", response_model=LiteResult)
def get_job_result(job_id: str) -> LiteResult:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=LiteErrorResponse(error=LiteError(code="job_not_found", message=f"Job not found: {job_id}")).model_dump(),
        )
    if job["status"] != JobStatus.SUCCEEDED.value or not job.get("result"):
        raise HTTPException(
            status_code=409,
            detail=LiteErrorResponse(error=LiteError(code="job_not_ready", message="Job result is not ready")).model_dump(),
        )
    return LiteResult.model_validate(job["result"])


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str) -> None:
    if not job_store.delete(job_id):
        raise HTTPException(
            status_code=404,
            detail=LiteErrorResponse(error=LiteError(code="job_not_found", message=f"Job not found: {job_id}")).model_dump(),
        )


@router.get("/export/{job_id}.csv")
def export_csv(job_id: str, merge_tables: bool = False) -> Response:
    job = job_store.get(job_id)
    if not job or not job.get("result"):
        raise HTTPException(status_code=404, detail="Job not found or no result")
    tables = job["result"].get("tables", [])
    content = export_tables_to_csv(tables, merge=merge_tables)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.csv"'},
    )


@router.get("/export/{job_id}.xlsx")
def export_xlsx(job_id: str, merge_tables: bool = False) -> Response:
    job = job_store.get(job_id)
    if not job or not job.get("result"):
        raise HTTPException(status_code=404, detail="Job not found or no result")
    tables = job["result"].get("tables", [])
    content = export_tables_to_xlsx(tables, merge=merge_tables)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.xlsx"'},
    )
