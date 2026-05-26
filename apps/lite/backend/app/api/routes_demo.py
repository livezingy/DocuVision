"""Demo routes: classification mappings, Supabase PoC, validation records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.job_store import job_store
from app.services.supabase_store import SupabaseStore, get_supabase_store

router = APIRouter(tags=["demo"])

_MAPPING_PATH = Path(__file__).resolve().parents[1] / "config" / "demo_classification_mappings.json"


class PersistResponse(BaseModel):
    persisted: bool
    backend: str
    document_id: Optional[str] = None
    transaction_count: int = 0
    message: str = ""


class ValidationRecord(BaseModel):
    document_id: str
    filename: str = ""
    status: str = "pending_validation"
    transaction_count: int = 0
    created_at: Optional[str] = None
    mapped_transactions: List[Dict[str, Any]] = Field(default_factory=list)


@router.get("/demo/classification-mappings")
def get_classification_mappings() -> Dict[str, Any]:
    if not _MAPPING_PATH.exists():
        raise HTTPException(status_code=404, detail="Mapping config not found")
    return json.loads(_MAPPING_PATH.read_text(encoding="utf-8"))


@router.get("/demo/supabase/status")
def supabase_status() -> Dict[str, Any]:
    store = get_supabase_store()
    return store.status()


@router.post("/demo/persist/{job_id}", response_model=PersistResponse)
async def persist_job_to_store(job_id: str) -> PersistResponse:
    job = job_store.get(job_id)
    if not job or not job.get("result"):
        raise HTTPException(status_code=404, detail="Job result not found")

    result = job["result"]
    store: SupabaseStore = get_supabase_store()
    outcome = await store.persist_extraction(
        job_id=job_id,
        filename=(result.get("input") or {}).get("filename", ""),
        mapped_transactions=result.get("mapped_transactions") or [],
        raw_result=result,
    )
    return PersistResponse(**outcome)


@router.get("/demo/validation/records", response_model=List[ValidationRecord])
async def list_validation_records(limit: int = 50) -> List[ValidationRecord]:
    store = get_supabase_store()
    rows = await store.list_validation_records(limit=limit)
    return [ValidationRecord(**row) for row in rows]
