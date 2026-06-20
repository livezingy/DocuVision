"""Webhook / integration layer with HTTP delivery."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class WebhookSubscription:
    subscription_id: str
    url: str
    events: List[str] = field(default_factory=lambda: ["task.completed", "batch.completed"])
    created_at: datetime = field(default_factory=datetime.now)
    active: bool = True
    secret: str = ""


class WebhookRegistry:
    def __init__(self) -> None:
        self._subs: Dict[str, WebhookSubscription] = {}

    def register(
        self,
        url: str,
        events: Optional[List[str]] = None,
        secret: str = "",
    ) -> WebhookSubscription:
        sub = WebhookSubscription(
            subscription_id=str(uuid.uuid4()),
            url=url.strip(),
            events=events or ["task.completed", "batch.completed"],
            secret=(secret or "").strip(),
        )
        self._subs[sub.subscription_id] = sub
        return sub

    def list_subscriptions(self) -> List[Dict[str, Any]]:
        return [
            {
                "subscription_id": s.subscription_id,
                "url": s.url,
                "events": s.events,
                "active": s.active,
                "has_secret": bool(s.secret),
            }
            for s in self._subs.values()
        ]

    def _targets_for_event(self, event: str) -> List[WebhookSubscription]:
        return [s for s in self._subs.values() if s.active and event in s.events]

    def dispatch_event(self, event: str, payload: Dict[str, Any]) -> List[str]:
        """Return URLs that would receive the event (sync compatibility)."""
        return [s.url for s in self._targets_for_event(event)]

    async def dispatch_event_async(
        self,
        event: str,
        payload: Dict[str, Any],
        *,
        max_retries: int = 2,
    ) -> List[Dict[str, Any]]:
        """POST webhook payloads to subscribed URLs."""
        import httpx

        targets = self._targets_for_event(event)
        if not targets:
            return []

        body = {"event": event, "payload": payload, "timestamp": datetime.utcnow().isoformat() + "Z"}
        body_bytes = json.dumps(body, ensure_ascii=True).encode("utf-8")
        results: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=15.0) as client:
            for sub in targets:
                headers = {"Content-Type": "application/json"}
                if sub.secret:
                    sig = hmac.new(sub.secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
                    headers["X-DocuVision-Signature"] = sig

                ok = False
                last_status = 0
                for attempt in range(max_retries + 1):
                    try:
                        resp = await client.post(sub.url, content=body_bytes, headers=headers)
                        last_status = resp.status_code
                        ok = 200 <= resp.status_code < 300
                        if ok:
                            break
                    except Exception as exc:
                        logger.warning(f"Webhook POST failed ({sub.url}): {exc}")
                        if attempt < max_retries:
                            await asyncio.sleep(0.5 * (attempt + 1))
                results.append(
                    {
                        "url": sub.url,
                        "subscription_id": sub.subscription_id,
                        "delivered": ok,
                        "status_code": last_status,
                    }
                )
                if ok:
                    logger.info(f"Webhook delivered event={event} url={sub.url}")
                else:
                    logger.warning(f"Webhook delivery failed event={event} url={sub.url} status={last_status}")
        return results


webhook_registry = WebhookRegistry()
