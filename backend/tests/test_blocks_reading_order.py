"""Contract tests for GET /api/v1/tasks/{id}/blocks reading_order passthrough.

GLM trial P0-B: the /blocks endpoint must surface the envelope view layer's
``reading_order`` so the frontend can render a reading-order overlay on
multi-column pages. These tests do not load Paddle/Qwen; a synthetic task
with a pre-built envelope is injected into the in-memory ``tasks`` dict.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main as main_module


def _make_task(task_id: str, elements: list) -> dict:
    """Build a minimal completed task with an envelope view layer."""
    return {
        "status": "completed",
        "file_name": "synthetic.pdf",
        "result": {"document_info": {"file_name": "synthetic.pdf"}},
        "envelope": {
            "preprocessing": {
                "coordinate_space": "preprocessed",
                "output_size": {"width": 1000, "height": 1400},
            },
            "view": {
                "pages": [
                    {
                        "page_num": 1,
                        "width": 1000,
                        "height": 1400,
                        "elements": elements,
                    }
                ],
            },
        },
    }


def _elem(eid: str, kind: str, reading_order: int) -> dict:
    """One view element with a valid polygon and reading_order."""
    return {
        "id": eid,
        "kind": kind,
        "polygon": [100, 100, 300, 100, 300, 200, 100, 200],
        "reading_order": reading_order,
        "processing_status": "succeeded",
        "payload": {"text": f"block {eid}", "confidence": 0.9},
    }


@pytest.fixture()
def client(monkeypatch):
    # Ensure no background processing interferes.
    async def _noop_process(task_id: str):
        pass
    monkeypatch.setattr(main_module, "process_document", _noop_process)
    return TestClient(main_module.app)


class TestBlocksReadingOrder:
    def test_reading_order_present_in_blocks(self, client):
        task_id = "ro-test-1"
        main_module.tasks[task_id] = _make_task(
            task_id,
            [_elem("e1", "text", 0), _elem("e2", "text", 1), _elem("e3", "figure", 2)],
        )
        try:
            resp = client.get(f"/api/v1/tasks/{task_id}/blocks?page_number=1")
            assert resp.status_code == 200, resp.text
            blocks = resp.json()["blocks"]
            assert len(blocks) == 3
            orders = [b["reading_order"] for b in blocks]
            assert orders == [0, 1, 2]
        finally:
            main_module.tasks.pop(task_id, None)

    def test_reading_order_absent_defaults_to_zero(self, client):
        """Legacy elements without reading_order must not break the endpoint."""
        task_id = "ro-test-2"
        elem = _elem("e1", "text", 5)
        del elem["reading_order"]  # simulate legacy data
        main_module.tasks[task_id] = _make_task(task_id, [elem])
        try:
            resp = client.get(f"/api/v1/tasks/{task_id}/blocks?page_number=1")
            assert resp.status_code == 200, resp.text
            blocks = resp.json()["blocks"]
            assert blocks[0]["reading_order"] == 0
        finally:
            main_module.tasks.pop(task_id, None)

    def test_incomplete_task_returns_400(self, client):
        task_id = "ro-test-3"
        main_module.tasks[task_id] = {"status": "processing"}
        try:
            resp = client.get(f"/api/v1/tasks/{task_id}/blocks")
            assert resp.status_code == 400
        finally:
            main_module.tasks.pop(task_id, None)

    def test_unknown_task_returns_404(self, client):
        resp = client.get("/api/v1/tasks/nonexistent/blocks")
        assert resp.status_code == 404
