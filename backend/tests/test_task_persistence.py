"""Single-task analyze-job persistence tests (v1.7).

Local, no Paddle / Torch / network. Imports service modules only
(not ``app.main``) so collection does not load GPU stacks.

Covers:
- analyze_jobs QueueStore round-trip
- completed persist -> empty dict -> load -> result + ZIP + figure file
- processing -> interrupted on load
- missing result.json -> missing_artifacts
- FIFO evicts oldest row and OUTPUT_DIR
- KIE field rewrite survives reload
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from app.services.pack_export_service import build_task_pack_zip
from app.services.persistence.analyze_job_store import AnalyzeJobStore
from app.services.persistence.queue_store import SqliteQueueStore

_MINI_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _result(*, invoice_total: str = "100") -> dict:
    return {
        "document_info": {"file_name": "demo.pdf"},
        "tables": [
            {
                "page": 1,
                "confidence": 0.87,
                "caption": "Ablation",
                "data": [["H1", "+pos"], ["a", "b"]],
            }
        ],
        "figures": {
            "figure_count": 1,
            "cropped_count": 1,
            "items": [
                {
                    "id": "p1_e3",
                    "page": 1,
                    "type": "figure",
                    "caption": "Flow",
                    "confidence": 0.9,
                    "is_merged": False,
                }
            ],
        },
        "quality": {"figure_count": 1, "figure_cropped_count": 1},
        "kie_fields": {"invoice_total": invoice_total},
        "view": {"fields": {"invoice_total": invoice_total}},
    }


def _completed_task(
    task_id: str,
    *,
    created_at: datetime | None = None,
    completed_at: datetime | None = None,
    invoice_total: str = "100",
) -> dict:
    now = created_at or datetime(2026, 9, 6, 10, 0, 0)
    done = completed_at or datetime(2026, 9, 6, 10, 5, 0)
    return {
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "message": "Processing completed",
        "created_at": now,
        "completed_at": done,
        "file_path": f"/tmp/{task_id}/demo.pdf",
        "file_name": "demo.pdf",
        "options": {"enable_figure_export": True},
        "result": _result(invoice_total=invoice_total),
    }


def _store(tmp_path: Path, *, keep_last_n: int = 50) -> tuple[SqliteQueueStore, AnalyzeJobStore, dict]:
    sqlite = SqliteQueueStore(db_path=tmp_path / "q.sqlite")
    jobs = AnalyzeJobStore(output_dir=tmp_path / "outputs", keep_last_n=keep_last_n)
    tasks: dict = {}
    jobs.bind(tasks)
    jobs.attach_store(sqlite)
    return sqlite, jobs, tasks


def _write_figure(output_dir: Path, task_id: str) -> Path:
    figures = output_dir / task_id / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    png = figures / "p1_e3.png"
    png.write_bytes(_MINI_PNG)
    return png


def test_analyze_jobs_queue_store_round_trip(tmp_path: Path) -> None:
    sqlite = SqliteQueueStore(db_path=tmp_path / "q.sqlite")
    doc = {
        "task_id": "t1",
        "status": "completed",
        "file_name": "demo.pdf",
        "file_path": "/tmp/t1/demo.pdf",
        "created_at": "2026-09-06T10:00:00",
        "completed_at": "2026-09-06T10:05:00",
        "options": {"enable_figure_export": True},
        "result_path": "/tmp/t1/result.json",
        "quality": {"figure_count": 1},
    }
    sqlite.save("analyze_jobs", "t1", doc)
    loaded = sqlite.load("analyze_jobs", "t1")
    assert loaded is not None
    assert loaded["task_id"] == "t1"
    assert loaded["options"] == {"enable_figure_export": True}
    assert loaded["quality"] == {"figure_count": 1}
    assert loaded["result_path"] == "/tmp/t1/result.json"
    sqlite.close()


def test_completed_survives_reload_and_zip(tmp_path: Path) -> None:
    sqlite, jobs, tasks = _store(tmp_path)
    task_id = "task1"
    _write_figure(jobs._output_dir, task_id)
    jobs.persist_task(_completed_task(task_id))

    assert (jobs.result_json_path(task_id)).is_file()
    row = sqlite.load("analyze_jobs", task_id)
    assert row is not None
    assert row["result_path"]
    assert "tables" not in (row.get("quality") or {})

    tasks.clear()
    jobs2 = AnalyzeJobStore(output_dir=jobs._output_dir, keep_last_n=50)
    jobs2.bind(tasks)
    jobs2.attach_store(sqlite)
    assert jobs2.load_from_db() == 1

    recovered = tasks[task_id]
    assert recovered["status"] == "completed"
    assert recovered["result"]["tables"][0]["caption"] == "Ablation"
    assert recovered["result"]["figures"]["items"][0]["id"] == "p1_e3"
    assert (jobs._output_dir / task_id / "figures" / "p1_e3.png").is_file()

    zip_path = Path(
        asyncio.run(
            build_task_pack_zip(
                recovered["result"],
                task_id,
                output_dir=str(tmp_path / "packs"),
                figures_dir=str(jobs._output_dir / task_id / "figures"),
            )
        )
    )
    assert zip_path.is_file()
    assert zip_path.read_bytes()[:2] == b"PK"
    sqlite.close()


def test_processing_becomes_interrupted(tmp_path: Path) -> None:
    sqlite, jobs, tasks = _store(tmp_path)
    task = {
        "task_id": "run1",
        "status": "processing",
        "created_at": datetime(2026, 9, 6, 11, 0, 0),
        "completed_at": None,
        "file_name": "demo.pdf",
        "file_path": "/tmp/run1/demo.pdf",
        "options": {},
        "result": None,
    }
    jobs.persist_task(task)
    assert not jobs.result_json_path("run1").exists()

    tasks.clear()
    jobs2 = AnalyzeJobStore(output_dir=jobs._output_dir)
    jobs2.bind(tasks)
    jobs2.attach_store(sqlite)
    jobs2.load_from_db()

    recovered = tasks["run1"]
    assert recovered["status"] == "interrupted"
    assert recovered["result"] is None
    assert "resubmit" in recovered["message"]
    sqlite.close()


def test_missing_result_json_is_missing_artifacts(tmp_path: Path) -> None:
    sqlite, jobs, tasks = _store(tmp_path)
    jobs.persist_task(_completed_task("gone1"))
    jobs.result_json_path("gone1").unlink()

    tasks.clear()
    jobs2 = AnalyzeJobStore(output_dir=jobs._output_dir)
    jobs2.bind(tasks)
    jobs2.attach_store(sqlite)
    jobs2.load_from_db()

    recovered = tasks["gone1"]
    assert recovered["status"] == "missing_artifacts"
    assert recovered["result"] is None
    sqlite.close()


def test_fifo_evicts_oldest_row_and_directory(tmp_path: Path) -> None:
    sqlite, jobs, tasks = _store(tmp_path, keep_last_n=2)
    base = datetime(2026, 9, 1, 8, 0, 0)
    for i, task_id in enumerate(("old1", "mid2", "new3")):
        _write_figure(jobs._output_dir, task_id)
        jobs.persist_task(
            _completed_task(
                task_id,
                created_at=base + timedelta(hours=i),
                completed_at=base + timedelta(hours=i, minutes=5),
            )
        )

    assert sqlite.load("analyze_jobs", "old1") is None
    assert not (jobs._output_dir / "old1").exists()
    assert sqlite.load("analyze_jobs", "mid2") is not None
    assert sqlite.load("analyze_jobs", "new3") is not None
    assert (jobs._output_dir / "mid2" / "result.json").is_file()
    assert (jobs._output_dir / "new3" / "figures" / "p1_e3.png").is_file()
    sqlite.close()


def test_kie_field_rewrite_survives_reload(tmp_path: Path) -> None:
    sqlite, jobs, tasks = _store(tmp_path)
    task = _completed_task("kie1", invoice_total="100")
    jobs.persist_task(task)

    task["result"]["kie_fields"]["invoice_total"] = "999"
    task["result"]["view"]["fields"]["invoice_total"] = "999"
    jobs.persist_task(task)

    tasks.clear()
    jobs2 = AnalyzeJobStore(output_dir=jobs._output_dir)
    jobs2.bind(tasks)
    jobs2.attach_store(sqlite)
    jobs2.load_from_db()

    recovered = tasks["kie1"]
    assert recovered["result"]["kie_fields"]["invoice_total"] == "999"
    assert recovered["result"]["view"]["fields"]["invoice_total"] == "999"
    sqlite.close()
