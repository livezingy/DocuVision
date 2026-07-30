"""Contract tests for table_template on analyze and table_step."""

import asyncio

import pytest

from app.orchestration.document_pipeline_orchestrator import DocumentPipelineOrchestrator, table_step


def make_orchestrator(services):
    async def call_maybe_async(func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    return DocumentPipelineOrchestrator(
        services=services,
        send_event=lambda *a, **k: asyncio.sleep(0),
        is_cancelled=lambda task_id: False,
        call_maybe_async=call_maybe_async,
        build_page_image_meta=lambda file_path, task_id=None, page_num=1: {
            "width_px": 1000,
            "height_px": 1000,
        },
    )


def test_table_step_applies_bank_statement_template(tmp_path):
    def fake_extract_with_meta(file_path, **kwargs):
        return {
            "tables": [
                {
                    "data": [
                        ["Date", "Description", "Amount", "Balance"],
                        ["02/01", "Deposit", "100.00", "1100.00"],
                    ],
                    "page": 1,
                }
            ],
            "meta": {"engine_used": "mock"},
        }

    services = {
        "table_service": type(
            "T", (), {"extract_with_meta": staticmethod(fake_extract_with_meta)}
        )(),
    }
    orch = make_orchestrator(services)
    ctx = {
        "task_id": "t-map",
        "task": {"file_name": "stmt.pdf"},
        "file_path": str(tmp_path / "stmt.pdf"),
        "options": {"enable_table": True, "table_template": "bank_statement"},
        "result": {"document_info": {}},
        "orchestrator": orch,
    }

    asyncio.run(table_step(ctx))

    rows = ctx["result"].get("mapped_table_rows") or []
    assert ctx["result"].get("table_template") == "bank_statement"
    assert len(rows) == 1
    assert rows[0].get("transaction_date") == "02/01"
    assert rows[0].get("description") == "Deposit"


def test_analyze_form_accepts_table_template(monkeypatch):
    # This test imports app.main, which imports paddle/paddlex at top level.
    # Phase A CI (kie-phase-a.yml) intentionally runs without Paddle, so skip
    # there; the full env (Cloud / local with paddle) runs it. Mirrors the
    # env-gating pattern used by test_live_api.py. Not a regression — this
    # guard aligns the test with its actual environment requirements.
    pytest.importorskip("paddle")
    from fastapi.testclient import TestClient

    from app import main as main_module

    async def _noop_process(task_id: str):
        task = main_module.tasks.get(task_id)
        if task:
            task["status"] = "completed"
            task["result"] = {"document_info": {"file_name": task.get("file_name", "")}}

    monkeypatch.setattr(main_module, "process_document", _noop_process)

    client = TestClient(main_module.app)
    response = client.post(
        "/api/v1/analyze",
        data={
            "enable_layout": "0",
            "enable_table": "1",
            "enable_kie": "0",
            "document_type": "general",
            "table_template": "bank_statement",
        },
        files={"file": ("tiny.pdf", b"%PDF-1.4\n", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    task_id = payload.get("task_id")
    assert task_id
    task = main_module.tasks[task_id]
    assert task["options"].get("table_template") == "bank_statement"
