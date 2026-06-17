"""Webhook / integration layer MVP."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class WebhookSubscription:
    subscription_id: str
    url: str
    events: List[str] = field(default_factory=lambda: ["task.completed", "batch.completed"])
    created_at: datetime = field(default_factory=datetime.now)
    active: bool = True


class WebhookRegistry:
    def __init__(self) -> None:
        self._subs: Dict[str, WebhookSubscription] = {}

    def register(self, url: str, events: Optional[List[str]] = None) -> WebhookSubscription:
        sub = WebhookSubscription(
            subscription_id=str(uuid.uuid4()),
            url=url.strip(),
            events=events or ["task.completed", "batch.completed"],
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
            }
            for s in self._subs.values()
        ]

    def dispatch_event(self, event: str, payload: Dict[str, Any]) -> List[str]:
        """Return URLs that would receive the event (delivery stub)."""
        targets = []
        for sub in self._subs.values():
            if sub.active and event in sub.events:
                targets.append(sub.url)
        return targets


webhook_registry = WebhookRegistry()
