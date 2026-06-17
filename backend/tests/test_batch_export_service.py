"""Unit tests for batch CSV export helpers."""

from datetime import datetime

from app.services.batch_export_service import build_kie_csv_rows, render_csv
from app.services.batch_service import BatchJob, BatchTask, BatchStatus, TaskStatus


def _sample_batch() -> BatchJob:
    batch = BatchJob(
        batch_id="test-batch",
        name="demo",
        status=BatchStatus.COMPLETED,
        options={"document_type": "invoice", "enable_kie": True},
        created_at=datetime.now(),
    )
    batch.total_tasks = 2
    t1 = BatchTask(task_id="t1", file_path="/a.png", file_name="a.png", status=TaskStatus.COMPLETED)
    t1.result = {
        "kie_fields": {"invoice_number": "INV-1", "total": "10"},
        "quality": {"kie_stage": "completed", "kie_production_hit": True, "kie_fields_count": 2},
    }
    t2 = BatchTask(task_id="t2", file_path="/b.png", file_name="b.png", status=TaskStatus.FAILED)
    t2.error = "boom"
    batch.tasks = [t1, t2]
    batch.completed_tasks = 1
    batch.failed_tasks = 1
    return batch


def test_build_kie_csv_has_core_columns() -> None:
    batch = _sample_batch()
    header, rows = build_kie_csv_rows(batch)
    assert "file_name" in header
    assert "kie_production_hit" in header
    assert len(rows) == 2
    csv_text = render_csv(header, rows)
    assert "INV-1" in csv_text
    assert "boom" in csv_text


def test_build_batch_xlsx_bytes() -> None:
    from app.services.batch_export_service import build_batch_xlsx_bytes

    batch = _sample_batch()
    batch.tasks[0].result["tables"] = [
        {"data": [["ColA", "ColB"], ["1", "2"]]},
    ]
    payload = build_batch_xlsx_bytes(batch, mode="all")
    assert isinstance(payload, bytes)
    assert len(payload) > 100
    assert payload[:2] == b"PK"
