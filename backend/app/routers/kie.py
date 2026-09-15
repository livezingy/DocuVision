"""KIE template routes: list / get / save schema templates (3 routes).

Moved verbatim from main.py (v1.8.2 C4). No ``prefix`` on the APIRouter —
paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Path as APIPath

router = APIRouter()


@router.get("/api/v1/kie/templates")
async def list_kie_templates():
    from app.services.kie.schema_templates import list_templates

    return {"templates": list_templates()}


@router.get("/api/v1/kie/templates/{template_id}")
async def get_kie_template(
    template_id: str = APIPath(..., pattern=r"^[A-Za-z0-9_-]+$"),
):
    from app.services.kie.schema_templates import load_template

    schema = load_template(template_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Template not found")
    return schema


@router.post("/api/v1/kie/templates/{template_id}")
async def save_kie_template(
    template_id: str = APIPath(..., pattern=r"^[A-Za-z0-9_-]+$"),
    body: Dict[str, Any] = Body(...),
):
    from app.services.kie.schema_templates import save_template

    try:
        save_template(template_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"template_id": template_id, "saved": True}
