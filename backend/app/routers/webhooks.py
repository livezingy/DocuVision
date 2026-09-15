"""Webhook routes: list subscriptions / register (2 routes) plus the
enabled-switch and admin-token guards only these routes use.

Moved verbatim from main.py (v1.8.2 C4). No ``prefix`` on the APIRouter —
paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from loguru import logger

from app.core.config import settings

router = APIRouter()


def _enforce_webhook_enabled() -> None:
    """Return 404 when the instance has webhooks disabled (process-level switch)."""
    if not settings.WEBHOOK_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")


def _enforce_webhook_admin_token(request: Request) -> None:
    """Validate ``X-DocuVision-Admin-Token`` against ``settings.WEBHOOK_ADMIN_TOKEN``.

    Fail-closed: when an admin token is configured, requests without a
    matching header are rejected with 401. An empty configured token is
    treated as "no auth required" only when webhooks are disabled (already
    gated by ``_enforce_webhook_enabled``); when enabled with an empty token,
    we still require the header to be absent-or-empty to avoid silently
    exposing registration, but log a warning.
    """
    expected = settings.WEBHOOK_ADMIN_TOKEN
    provided = request.headers.get("X-DocuVision-Admin-Token", "")
    if expected:
        if not provided or provided != expected:
            raise HTTPException(status_code=401, detail="Invalid admin token")
    else:
        # Token not configured: fail-closed to avoid open registration.
        logger.warning(
            "WEBHOOK_ENABLED=true but WEBHOOK_ADMIN_TOKEN is empty; "
            "rejecting webhook admin request. Set WEBHOOK_ADMIN_TOKEN to allow registration."
        )
        raise HTTPException(status_code=401, detail="Admin token not configured")


@router.get("/api/v1/webhooks")
async def list_webhooks(request: Request):
    _enforce_webhook_enabled()
    _enforce_webhook_admin_token(request)
    from app.services.webhook_service import webhook_registry

    return {"subscriptions": webhook_registry.list_subscriptions()}


@router.post("/api/v1/webhooks")
async def register_webhook(
    request: Request,
    url: str = Form(...),
    events: str = Form("task.completed,batch.completed"),
    secret: str = Form(""),
):
    _enforce_webhook_enabled()
    _enforce_webhook_admin_token(request)
    from app.services.webhook_service import webhook_registry

    event_list = [e.strip() for e in events.split(",") if e.strip()]
    try:
        sub = webhook_registry.register(url, event_list, secret=secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "subscription_id": sub.subscription_id,
        "url": sub.url,
        "events": sub.events,
    }
