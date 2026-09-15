"""HITL review routes: list / get / resolve (3 routes).

Moved verbatim from main.py (v1.8.2 C4). No ``prefix`` on the APIRouter —
paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from app.core.runtime import _apply_kie_fields_to_task, tasks
from app.models.api_models import HitlResolveModel

router = APIRouter()


@router.get("/api/v1/hitl/reviews")
async def list_hitl_reviews(limit: int = 50, include_payload: bool = False):
    from app.services.hitl_queue import hitl_queue

    return {"reviews": hitl_queue.list_pending(limit=limit, include_payload=include_payload)}


@router.get("/api/v1/hitl/reviews/{review_id}")
async def get_hitl_review(review_id: str):
    from app.services.hitl_queue import hitl_queue

    item = hitl_queue.get(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review not found")
    return {
        "review_id": item.review_id,
        "task_id": item.task_id,
        "file_name": item.file_name,
        "reason": item.reason,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "payload": item.payload,
    }


@router.post("/api/v1/hitl/reviews/{review_id}/resolve")
async def resolve_hitl_review(
    review_id: str,
    status: str = "approved",
    body: Optional[HitlResolveModel] = None,
):
    from app.services.hitl_queue import hitl_queue

    item = hitl_queue.get(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review not found")

    resolved_status = (body.status if body and body.status else status).strip().lower()
    if resolved_status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be approved or rejected")

    if resolved_status == "approved":
        task_id = item.task_id
        if task_id in tasks:
            if body and body.corrected_fields is not None:
                _apply_kie_fields_to_task(tasks[task_id], body.corrected_fields)
            else:
                result = tasks[task_id].get("result")
                if isinstance(result, dict):
                    validation = dict(result.get("kie_validation") or {})
                    validation["manual_reviewed"] = True
                    validation["validation_passed"] = True
                    result["kie_validation"] = validation

    corrected = body.corrected_fields if body and body.corrected_fields is not None else None
    item = await hitl_queue.resolve(review_id, status=resolved_status, edited_fields=corrected)
    if not item:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"review_id": review_id, "status": item.status, "task_id": item.task_id}
