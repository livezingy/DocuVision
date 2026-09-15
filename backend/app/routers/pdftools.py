"""PDF tools routes: split / merge / metadata / searchable / form-fill (5 routes).

Moved verbatim from main.py (v1.8.2 C4). No ``prefix`` on the APIRouter —
paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

import os
import uuid
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

router = APIRouter()


@router.post("/api/v1/pdf-tools/split")
async def pdf_tools_split(file: UploadFile = File(...), pages: str = Form("")):
    import json
    import tempfile

    from app.services.pdf_tools_service import coerce_page_list, split_pdf

    page_list = None
    if pages.strip():
        try:
            page_list = coerce_page_list(json.loads(pages))
        except Exception:
            page_list = coerce_page_list(
                [int(p.strip()) for p in pages.split(",") if p.strip().isdigit()]
            )

    suffix = os.path.splitext(file.filename or "")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        in_path = tmp.name
    out_dir = os.path.join(tempfile.gettempdir(), f"split_{uuid.uuid4().hex[:8]}")
    try:
        outputs = split_pdf(in_path, out_dir, pages=page_list)
        if len(outputs) == 1 and os.path.isfile(outputs[0]):
            base = os.path.splitext(file.filename or "document")[0]
            page_num = (page_list or [1])[0]
            return FileResponse(
                outputs[0],
                filename=f"{base}_page_{page_num}.pdf",
                media_type="application/pdf",
            )
        return {"pages": outputs, "count": len(outputs)}
    finally:
        try:
            os.unlink(in_path)
        except OSError:
            pass


@router.post("/api/v1/pdf-tools/merge")
async def pdf_tools_merge(files: List[UploadFile] = File(...)):
    import tempfile

    from app.services.pdf_tools_service import merge_pdfs

    paths = []
    try:
        for upload in files:
            suffix = os.path.splitext(upload.filename or "")[1] or ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await upload.read())
                paths.append(tmp.name)
        out_path = os.path.join(tempfile.gettempdir(), f"merged_{uuid.uuid4().hex[:8]}.pdf")
        merge_pdfs(paths, out_path)
        return FileResponse(out_path, filename="merged.pdf", media_type="application/pdf")
    finally:
        for path in paths:
            try:
                os.unlink(path)
            except OSError:
                pass


@router.post("/api/v1/pdf-tools/metadata")
async def pdf_tools_metadata(file: UploadFile = File(...)):
    import tempfile

    from app.services.pdf_tools_service import read_pdf_metadata

    suffix = os.path.splitext(file.filename or "")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        return read_pdf_metadata(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("/api/v1/pdf-tools/searchable")
async def pdf_tools_searchable(file: UploadFile = File(...), text: str = Form("")):
    raise HTTPException(
        status_code=501,
        detail="Not Implemented: searchable PDF OCR text layer not yet supported",
    )


@router.post("/api/v1/pdf-tools/form-fill")
async def pdf_tools_form_fill(
    file: UploadFile = File(...),
    field_values: str = Form("{}"),
):
    import json
    import tempfile

    from app.services.pdf_tools_service import fill_acroform

    try:
        values = json.loads(field_values)
    except Exception:
        values = {}
    if not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="field_values must be a JSON object")

    suffix = os.path.splitext(file.filename or "")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        in_path = tmp.name
    out_path = os.path.join(tempfile.gettempdir(), f"filled_{uuid.uuid4().hex[:8]}.pdf")
    try:
        fill_acroform(in_path, out_path, {str(k): str(v) for k, v in values.items()})
        return FileResponse(out_path, filename="filled.pdf", media_type="application/pdf")
    finally:
        try:
            os.unlink(in_path)
        except OSError:
            pass
