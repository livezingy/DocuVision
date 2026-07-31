"""Queue persistence tests (Batch + HITL).

These tests run locally without Paddle/Torch/network. They import only the
service modules (not ``app.main``) to avoid triggering GPU/Paddle imports.

Covers:
- SqliteQueueStore round-trip (save/load/load_all/delete)
- BatchService restart recovery (processing -> paused, task processing -> pending)
- HitlReviewQueue restart recovery (edited_fields + resolved_at intact)
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from app.services.batch_service import BatchService, BatchStatus, TaskStatus
from app.services.hitl_queue import HitlReviewQueue
from app.services.persistence.queue_store import SqliteQueueStore


# ---------------------------------------------------------------------------
# SqliteQueueStore round-trip
# ---------------------------------------------------------------------------


def test_sqlite_queue_store_round_trip(tmp_path: Path) -> None:
    store = SqliteQueueStore(db_path=tmp_path / "q.sqlite")

    batch_doc = {
        "batch_id": "b1",
        "name": "batch-1",
        "status": "pending",
        "options": {"enable_kie": True, "kie_pages": "1"},
        "tasks": [{"task_id": "t1", "file_name": "a.pdf", "status": "pending"}],
        "total_tasks": 1,
        "completed_tasks": 0,
        "failed_tasks": 0,
        "created_at": "2026-07-31T10:00:00",
        "started_at": None,
        "completed_at": None,
    }
    store.save("batch_jobs", "b1", batch_doc)

    loaded = store.load("batch_jobs", "b1")
    assert loaded is not None
    assert loaded["batch_id"] == "b1"
    assert loaded["options"] == {"enable_kie": True, "kie_pages": "1"}
    assert loaded["tasks"] == [{"task_id": "t1", "file_name": "a.pdf", "status": "pending"}]

    review_doc = {
        "review_id": "r1",
        "task_id": "t1",
        "file_name": "a.pdf",
        "reason": "kie_validation_failed",
        "payload": {"validation": {"validation_passed": False}},
        "edited_fields": {"invoice_date": "2026-07-31"},
        "status": "approved",
        "created_at": "2026-07-31T10:01:00",
        "resolved_at": "2026-07-31T10:02:00",
    }
    store.save("hitl_reviews", "r1", review_doc)

    all_reviews = store.load_all("hitl_reviews")
    assert len(all_reviews) == 1
    assert all_reviews[0]["edited_fields"] == {"invoice_date": "2026-07-31"}
    assert all_reviews[0]["payload"] == {"validation": {"validation_passed": False}}

    # Upsert: save again with changed status
    review_doc["status"] = "rejected"
    store.save("hitl_reviews", "r1", review_doc)
    assert store.load("hitl_reviews", "r1")["status"] == "rejected"
    assert len(store.load_all("hitl_reviews")) == 1

    # Delete
    store.delete("batch_jobs", "b1")
    assert store.load("batch_jobs", "b1") is None
    store.delete("hitl_reviews", "r1")
    assert store.load("hitl_reviews", "r1") is None
    assert store.load_all("hitl_reviews") == []

    store.close()


def test_sqlite_queue_store_unknown_table_raises(tmp_path: Path) -> None:
    store = SqliteQueueStore(db_path=tmp_path / "q.sqlite")
    with pytest.raises(ValueError):
        store.save("nope", "k", {})
    with pytest.raises(ValueError):
        store.load("nope", "k")
    with pytest.raises(ValueError):
        store.load_all("nope")
    with pytest.raises(ValueError):
        store.delete("nope", "k")
    store.close()


# ---------------------------------------------------------------------------
# BatchService restart recovery
# ---------------------------------------------------------------------------


def test_batch_service_restart_recovery(tmp_path: Path) -> None:
    store = SqliteQueueStore(db_path=tmp_path / "batch.sqlite")
    svc1 = BatchService(max_concurrent=2)
    svc1.attach_store(store)

    batch = svc1.create_batch(
        name="restart-test",
        files=[{"file_path": "/tmp/a.pdf", "file_name": "a.pdf"}],
        options={"enable_kie": False},
    )
    batch_id = batch.batch_id

    # Simulate a crash mid-flight: batch is PROCESSING, one task is PROCESSING.
    batch.status = BatchStatus.PROCESSING
    batch.started_at = datetime.now()
    batch.tasks[0].status = TaskStatus.PROCESSING
    batch.tasks[0].started_at = datetime.now()
    svc1._persist(batch)  # write the "crashed" snapshot directly

    # Second service instance sharing the same store (simulates restart).
    svc2 = BatchService(max_concurrent=2)
    svc2.attach_store(store)
    loaded = svc2.load_from_db()
    assert loaded == 1

    recovered = svc2.get_batch(batch_id)
    assert recovered is not None
    assert recovered.status == BatchStatus.PAUSED  # processing -> paused
    assert recovered.name == "restart-test"
    assert recovered.tasks[0].status == TaskStatus.PENDING  # processing -> pending
    assert recovered.tasks[0].task_id == batch.tasks[0].task_id

    # Runtime-only state must be empty after load.
    assert svc2._active_batches == {}
    assert svc2._cancelled_batches == set()
    assert svc2._paused_batches == set()

    store.close()


def test_batch_service_delete_persists(tmp_path: Path) -> None:
    store = SqliteQueueStore(db_path=tmp_path / "batch.sqlite")
    svc = BatchService(max_concurrent=1)
    svc.attach_store(store)

    batch = svc.create_batch(name="del", files=[{"file_path": "x", "file_name": "x.pdf"}])
    assert store.load("batch_jobs", batch.batch_id) is not None

    assert svc.delete_batch(batch.batch_id) is True
    assert store.load("batch_jobs", batch.batch_id) is None
    store.close()


# ---------------------------------------------------------------------------
# HitlReviewQueue restart recovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hitl_queue_restart_recovery(tmp_path: Path) -> None:
    store = SqliteQueueStore(db_path=tmp_path / "hitl.sqlite")
    q1 = HitlReviewQueue()
    q1.attach_store(store)

    item = await q1.enqueue(
        task_id="task-1",
        file_name="invoice.pdf",
        reason="kie_validation_failed",
        payload={"validation": {"validation_passed": False}, "fields": {"total": "100"}},
    )
    review_id = item.review_id

    edited = {"total": "120.50", "invoice_date": "2026-07-31"}
    resolved = await q1.resolve(review_id, status="approved", edited_fields=edited)
    assert resolved is not None
    assert resolved.status == "approved"
    assert resolved.edited_fields == edited
    assert resolved.resolved_at is not None

    # Second queue instance sharing the same store (simulates restart).
    q2 = HitlReviewQueue()
    q2.attach_store(store)
    loaded = q2.load_from_db()
    assert loaded == 1

    recovered = q2.get(review_id)
    assert recovered is not None
    assert recovered.status == "approved"
    assert recovered.edited_fields == edited
    assert recovered.resolved_at is not None
    # Original payload must be preserved (not overwritten by edited_fields).
    assert recovered.payload["fields"] == {"total": "100"}
    assert recovered.task_id == "task-1"
    assert recovered.file_name == "invoice.pdf"

    store.close()


@pytest.mark.asyncio
async def test_hitl_queue_pending_preserved_on_restart(tmp_path: Path) -> None:
    store = SqliteQueueStore(db_path=tmp_path / "hitl.sqlite")
    q1 = HitlReviewQueue()
    q1.attach_store(store)

    item = await q1.enqueue("t2", "b.pdf", "low_confidence", {"k": "v"})
    # Do NOT resolve -> stays pending.

    q2 = HitlReviewQueue()
    q2.attach_store(store)
    q2.load_from_db()

    pending = q2.list_pending()
    assert len(pending) == 1
    assert pending[0]["review_id"] == item.review_id
    assert pending[0]["status"] if "status" in pending[0] else True
    store.close()
