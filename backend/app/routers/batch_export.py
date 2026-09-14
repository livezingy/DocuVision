"""Batch export routes: summary / results / export.csv / export.xlsx /
export.json (5 routes).

Moved verbatim from main.py (v1.8.2 C3). No ``prefix`` on the APIRouter —
paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from loguru import logger

from app.core.runtime import batch_service
from app.services.batch_export_service import (
    build_batch_xlsx_bytes,
    build_failure_csv_rows,
    build_json_bundle,
    build_kie_csv_rows,
    build_summary_csv_rows,
    render_csv,
)

router = APIRouter()


@router.get("/api/v1/batch/{batch_id}/summary")
async def get_batch_summary(batch_id: str):
    """Get batch job summary"""
    try:
        return batch_service.get_batch_summary(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/v1/batch/{batch_id}/results")
async def get_batch_results(batch_id: str):
    """Get all results from a batch"""
    try:
        return {"results": batch_service.get_batch_results(batch_id)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/v1/batch/{batch_id}/export.csv")
async def export_batch_csv(batch_id: str, mode: str = "kie", validation_passed_only: bool = False):
    """Download aggregated batch results as CSV (mode: kie, summary, failures)."""
    batch = batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    mode_norm = (mode or "kie").strip().lower()
    export_opts = dict(batch.options or {})
    if validation_passed_only:
        export_opts["validation_passed_only"] = True
    if mode_norm == "summary":
        header, rows = build_summary_csv_rows(batch)
    elif mode_norm in ("failures", "failure"):
        header, rows = build_failure_csv_rows(batch)
    else:
        header, rows = build_kie_csv_rows(batch, options=export_opts)

    csv_text = render_csv(header, rows)
    filename = f"batch_{batch_id}_{mode_norm}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/v1/batch/{batch_id}/export.xlsx")
async def export_batch_xlsx(batch_id: str, mode: str = "all"):
    """Download aggregated batch results as Excel (mode: all, kie, tables, summary)."""
    batch = batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    mode_norm = (mode or "all").strip().lower()
    if mode_norm not in {"all", "kie", "tables", "summary"}:
        raise HTTPException(status_code=400, detail="Invalid mode; use all, kie, tables, or summary")

    try:
        payload = build_batch_xlsx_bytes(batch, mode=mode_norm)
    except Exception as exc:
        logger.error(f"Batch Excel export failed: {exc}")
        raise HTTPException(status_code=500, detail="Batch Excel export failed") from exc

    filename = f"batch_{batch_id}_{mode_norm}.xlsx"
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/v1/batch/{batch_id}/export.json")
async def export_batch_json(batch_id: str):
    """Download full batch results as JSON bundle."""
    import json

    batch = batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    payload = json.dumps(build_json_bundle(batch), ensure_ascii=False, indent=2)
    filename = f"batch_{batch_id}.json"
    return Response(
        content=payload,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
