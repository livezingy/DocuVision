"""Contract tests for POST /api/v1/documents:analyze Form parameter parity
with legacy POST /api/v1/analyze.

These tests do not load Paddle/Qwen; ``process_document`` is monkeypatched so
the background task returns immediately. The assertions verify that Form
parameters declared on ``analyze_document_v1`` are propagated into the
stored task ``options`` dict.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main as main_module


def _install_nop_process(monkeypatch) -> None:
    async def _noop_process(task_id: str):
        task = main_module.tasks.get(task_id)
        if task:
            task["status"] = "completed"
            task["result"] = {"document_info": {"file_name": task.get("file_name", "")}}

    monkeypatch.setattr(main_module, "process_document", _noop_process)


def _post_phase1(client: TestClient, data: dict) -> dict:
    response = client.post(
        "/api/v1/documents:analyze",
        data=data,
        files={"file": ("tiny.pdf", b"%PDF-1.4\n", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["job_id"], payload
    return main_module.tasks[payload["job_id"]]


def test_phase1_defaults_match_legacy_defaults(monkeypatch):
    _install_nop_process(monkeypatch)
    client = TestClient(main_module.app)
    task = _post_phase1(client, {})
    opts = task["options"]
    # Defaults must mirror legacy /api/v1/analyze defaults, not the old
    # hardcoded Phase1 behavior (which forced enable_layout/enable_table True
    # but dropped every other toggle).
    assert opts["enable_layout"] is True
    assert opts["enable_table"] is True
    assert opts["enable_formula"] is False
    assert opts["enable_seal"] is False
    assert opts["enable_kie"] is False
    assert opts["document_type"] == "auto"
    assert opts["language"] == "en"
    assert opts["return_raw"] is False
    assert opts["enable_hitl"] is True
    assert opts["kie_pages"] == "1"
    assert opts["kie_query_fields"] == []


def test_phase1_propagates_engine_and_formula_params(monkeypatch):
    _install_nop_process(monkeypatch)
    client = TestClient(main_module.app)
    task = _post_phase1(
        client,
        {
            "enable_layout": "0",
            "enable_table": "1",
            "enable_formula": "1",
            "enable_seal": "1",
            "language": "ch",
            "ocr_engine": "paddleocr",
            "layout_engine": "paddlex",
            "table_engine": "camelot",
            "table_allow_fullpage_fallback": "1",
            "formula_disable_layout": "1",
            "formula_disable_preprocess": "1",
            "formula_two_stage_threshold_retry": "0",
            "formula_primary_layout_threshold": "0.7",
            "formula_fallback_layout_threshold": "0.3",
            "formula_layout_threshold": "0.4",
            "pipeline_formula_batch_size": "2",
            "return_raw": "1",
        },
    )
    opts = task["options"]
    assert opts["enable_layout"] is False
    assert opts["enable_table"] is True
    assert opts["enable_formula"] is True
    assert opts["enable_seal"] is True
    assert opts["language"] == "ch"
    assert opts["ocr_engine"] == "paddleocr"
    assert opts["layout_engine"] == "paddlex"
    assert opts["table_engine"] == "camelot"
    assert opts["table_allow_fullpage_fallback"] is True
    assert opts["formula_disable_layout"] is True
    assert opts["formula_disable_preprocess"] is True
    assert opts["formula_two_stage_threshold_retry"] is False
    assert opts["formula_primary_layout_threshold"] == pytest.approx(0.7)
    assert opts["formula_fallback_layout_threshold"] == pytest.approx(0.3)
    assert opts["formula_layout_threshold"] == pytest.approx(0.4)
    assert opts["pipeline_formula_batch_size"] == 2
    assert opts["return_raw"] is True


def test_phase1_table_template_and_hitl_toggle(monkeypatch):
    _install_nop_process(monkeypatch)
    client = TestClient(main_module.app)
    task = _post_phase1(
        client,
        {
            "table_template": "Bank_Statement",
            "enable_hitl": "0",
        },
    )
    opts = task["options"]
    assert opts["table_template"] == "bank_statement"
    assert opts["enable_hitl"] is False


def test_phase1_auto_enables_kie_for_invoice_doc_type(monkeypatch):
    _install_nop_process(monkeypatch)
    client = TestClient(main_module.app)
    task = _post_phase1(client, {"document_type": "invoice"})
    opts = task["options"]
    assert opts["enable_kie"] is True
