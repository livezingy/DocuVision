"""Tests for demo API routes."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.job_store import job_store


client = TestClient(app)


def test_classification_mappings_endpoint():
    res = client.get("/api/v1/lite/demo/classification-mappings")
    assert res.status_code == 200
    data = res.json()
    assert "rules" in data
    assert data["default_internal_code"] == "UNMAPPED"


def test_supabase_status_endpoint():
    res = client.get("/api/v1/lite/demo/supabase/status")
    assert res.status_code == 200
    data = res.json()
    assert data["backend"] in {"local_json", "supabase"}
    assert "enabled" in data


def test_persist_job_local_fallback(tmp_path, monkeypatch):
    import app.services.supabase_store as supabase_module
    from app.core import config

    monkeypatch.setattr(config.settings, "SUPABASE_URL", "")
    monkeypatch.setattr(config.settings, "SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setattr(config.settings, "DEMO_VALIDATION_DIR", str(tmp_path))
    supabase_module._store = None

    job_id = job_store.create()
    job_store.save_result(
        job_id,
        {
            "job_id": job_id,
            "input": {"filename": "demo.pdf"},
            "mapped_transactions": [{"description": "Software", "amount": "10", "internal_code": "X"}],
        },
    )
    res = client.post(f"/api/v1/lite/demo/persist/{job_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["persisted"] is True
    assert body["backend"] == "local_json"
    assert body["transaction_count"] == 1

    listed = client.get("/api/v1/lite/demo/validation/records")
    assert listed.status_code == 200
    records = listed.json()
    assert len(records) >= 1
