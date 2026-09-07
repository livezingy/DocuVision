"""HITL low-confidence review queue.

In-memory index backed by an optional ``QueueStore`` for crash/restart
recovery. The module-level singleton ``hitl_queue`` is constructed without a
store; ``main.py`` attaches a ``SqliteQueueStore`` at startup via
``attach_store`` and calls ``load_from_db`` to rebuild the in-memory index.

Persistence scope (v1.5):
- ``ReviewItem`` rows (status, payload, edited_fields, resolved_at) survive
  restart.
- The ``tasks`` dict in ``main.py`` is persisted separately by
  ``AnalyzeJobStore`` (v1.7), not by this queue.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from loguru import logger


class _StoreLike(Protocol):
    def save(self, table: str, key: str, document: dict) -> None: ...
    def load_all(self, table: str) -> List[dict]: ...


@dataclass
class ReviewItem:
    review_id: str
    task_id: str
    file_name: str
    reason: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    edited_fields: Optional[Dict[str, Any]] = None
    resolved_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewItem":
        created_raw = d.get("created_at")
        resolved_raw = d.get("resolved_at")

        def _parse_dt(v: Any) -> Optional[datetime]:
            if not v:
                return None
            if isinstance(v, datetime):
                return v
            try:
                return datetime.fromisoformat(str(v))
            except (ValueError, TypeError):
                return None

        return cls(
            review_id=str(d["review_id"]),
            task_id=str(d["task_id"]),
            file_name=str(d["file_name"]),
            reason=str(d["reason"]),
            payload=_as_dict(d.get("payload")),
            status=str(d.get("status", "pending")),
            created_at=_parse_dt(created_raw) or datetime.now(),
            edited_fields=_as_dict(d.get("edited_fields")) if d.get("edited_fields") is not None else None,
            resolved_at=_parse_dt(resolved_raw),
        )

    def to_store_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "task_id": self.task_id,
            "file_name": self.file_name,
            "reason": self.reason,
            "payload": self.payload,
            "edited_fields": self.edited_fields,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


def _as_dict(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        if not v:
            return {}
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


class HitlReviewQueue:
    """HITL review queue with optional SQLite-backed persistence."""

    TABLE = "hitl_reviews"

    def __init__(self) -> None:
        self._items: Dict[str, ReviewItem] = {}
        self._store: Optional[_StoreLike] = None

    # ------------------------------------------------------------------
    # Store wiring
    # ------------------------------------------------------------------
    def attach_store(self, store: _StoreLike) -> None:
        """Attach a ``QueueStore`` and load existing rows into memory."""
        self._store = store

    def load_from_db(self) -> int:
        """Rebuild ``_items`` from the store. Returns the number of rows loaded."""
        if self._store is None:
            return 0
        rows = self._store.load_all(self.TABLE)
        loaded = 0
        for row in rows:
            try:
                item = ReviewItem.from_dict(row)
                self._items[item.review_id] = item
                loaded += 1
            except (KeyError, ValueError) as exc:
                logger.warning("hitl_reviews row skipped ({}): {}", row.get("review_id", "?"), exc)
        logger.info("HitlReviewQueue loaded {} review(s) from store", loaded)
        return loaded

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _persist(self, item: ReviewItem) -> None:
        if self._store is None:
            return
        self._store.save(self.TABLE, item.review_id, item.to_store_dict())

    async def _persist_async(self, item: ReviewItem) -> None:
        if self._store is None:
            return
        await asyncio.to_thread(self._persist, item)

    # ------------------------------------------------------------------
    # Queue operations
    # ------------------------------------------------------------------
    async def enqueue(
        self,
        task_id: str,
        file_name: str,
        reason: str,
        payload: Dict[str, Any],
    ) -> ReviewItem:
        item = ReviewItem(
            review_id=str(uuid.uuid4()),
            task_id=task_id,
            file_name=file_name,
            reason=reason,
            payload=payload,
        )
        self._items[item.review_id] = item
        await self._persist_async(item)
        return item

    def list_pending(self, limit: int = 50, include_payload: bool = False) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for item in self._items.values():
            if item.status != "pending":
                continue
            entry = {
                "review_id": item.review_id,
                "task_id": item.task_id,
                "file_name": item.file_name,
                "reason": item.reason,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            if include_payload:
                entry["payload"] = item.payload
            out.append(entry)
            if len(out) >= limit:
                break
        return out

    def get(self, review_id: str) -> Optional[ReviewItem]:
        return self._items.get(review_id)

    async def resolve(
        self,
        review_id: str,
        status: str = "approved",
        edited_fields: Optional[Dict[str, Any]] = None,
    ) -> Optional[ReviewItem]:
        item = self._items.get(review_id)
        if not item:
            return None
        item.status = status
        if edited_fields is not None:
            item.edited_fields = edited_fields
        item.resolved_at = datetime.now()
        await self._persist_async(item)
        return item


hitl_queue = HitlReviewQueue()
