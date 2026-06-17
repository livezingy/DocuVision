"""Lite batch API (table-only)."""

from __future__ import annotations

import json
import os
import uuid
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from docuvision_core.export.tables import export_tables_to_csv, export_tables_to_xlsx

from app.core.config import settings
from app.services.lite_batch_service import lite_batch_service

router = APIRouter(tags=["lite-batch"])


@router.post("/batch")
async def create_lite_batch(
    name: str = Form(...),
    files: List[UploadFile] = File(...),
    options: str = Form('{"table_only": true}'),
):
    try:
        opts = json.loads(options)
    except Exception:
        opts = {"table_only": True}
    if not isinstance(opts, dict):
        opts = {"table_only": True}

    batch_dir = os.path.join(settings.JOB_DATA_DIR, "batches", f"lite_batch_{uuid.uuid4().hex[:8]}")
    os.makedirs(batch_dir, exist_ok=True)
    file_list = []
    for upload in files:
        ext = os.path.splitext(upload.filename or "")[1].lower()
        if ext != ".pdf":
            continue
        path = os.path.join(batch_dir, upload.filename or f"file{len(file_list)}.pdf")
        with open(path, "wb") as fh:
            fh.write(await upload.read())
        file_list.append({"file_path": path, "file_name": os.path.basename(path)})

    if not file_list:
        raise HTTPException(status_code=400, detail="No valid PDF files provided")

    batch = lite_batch_service.create_batch(name, file_list, opts)
    return batch.to_dict()


@router.post("/batch/{batch_id}/start")
async def start_lite_batch(batch_id: str):
    batch = lite_batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    await lite_batch_service.start_batch(batch_id)
    batch = lite_batch_service.get_batch(batch_id)
    return batch.to_dict() if batch else {}


@router.get("/batch/{batch_id}")
async def get_lite_batch(batch_id: str):
    batch = lite_batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    payload = batch.to_dict()
    payload["progress"] = batch.get_progress()
    return payload


@router.get("/batch/{batch_id}/export.csv")
async def export_lite_batch_csv(batch_id: str):
    batch = lite_batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    all_tables = []
    for task in batch.tasks:
        for table in (task.result or {}).get("tables") or []:
            all_tables.append(table)
    body = export_tables_to_csv(all_tables, merge=False)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="lite_batch_{batch_id}.csv"'},
    )


@router.get("/batch/{batch_id}/export.xlsx")
async def export_lite_batch_xlsx(batch_id: str):
    batch = lite_batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    all_tables = []
    for task in batch.tasks:
        for table in (task.result or {}).get("tables") or []:
            all_tables.append(table)
    payload = export_tables_to_xlsx(all_tables, merge=False)
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="lite_batch_{batch_id}.xlsx"'},
    )
