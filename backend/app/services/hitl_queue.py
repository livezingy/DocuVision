"""HITL low-confidence review queue (in-memory MVP)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ReviewItem:
    review_id: str
    task_id: str
    file_name: str
    reason: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)


class HitlReviewQueue:
    def __init__(self) -> None:
        self._items: Dict[str, ReviewItem] = {}

    def enqueue(self, task_id: str, file_name: str, reason: str, payload: Dict[str, Any]) -> ReviewItem:
        item = ReviewItem(
            review_id=str(uuid.uuid4()),
            task_id=task_id,
            file_name=file_name,
            reason=reason,
            payload=payload,
        )
        self._items[item.review_id] = item
        return item

    def list_pending(self, limit: int = 50) -> List[Dict[str, Any]]:
        out = []
        for item in self._items.values():
            if item.status != "pending":
                continue
            out.append(
                {
                    "review_id": item.review_id,
                    "task_id": item.task_id,
                    "file_name": item.file_name,
                    "reason": item.reason,
                    "created_at": item.created_at.isoformat(),
                }
            )
            if len(out) >= limit:
                break
        return out

    def resolve(self, review_id: str, status: str = "approved") -> Optional[ReviewItem]:
        item = self._items.get(review_id)
        if not item:
            return None
        item.status = status
        return item


hitl_queue = HitlReviewQueue()
