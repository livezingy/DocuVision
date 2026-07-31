"""Tests for DocuVision Lite API (Phase A)."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.lite_result import (
    LITE_API_VERSION,
    LITE_SCHEMA_VERSION,
    JobStatus,
    LiteHealthResponse,
    LiteResult,
)

client = TestClient(app)

LITE_RESULT_TOP_KEYS = {
    "schema_version",
    "api_version",
    "job_id",
    "status",
    "created_at",
    "completed_at",
    "processing_ms",
    "input",
    "routing",
    "quality",
    "tables",
    "ocr",
    "text_preview",
    "exports",
    "warnings",
    "hints",
    "transactions",
    "mapped_transactions",
    "mapped_table_rows",
    "table_template",
    "error",
}


def test_health_returns_ok():
    response = client.get("/api/v1/lite/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "docuvision-lite"
    assert data["api_version"] == LITE_API_VERSION
    assert data["profile"] == "cpu"
    assert "engines" in data
    assert "limits" in data
    LiteHealthResponse.model_validate(data)


def test_engines_lists_pdfplumber_and_camelot():
    response = client.get("/api/v1/lite/engines")
    assert response.status_code == 200
    data = response.json()
    engine_ids = {e["id"] for e in data["engines"]}
    assert "pdfplumber" in engine_ids
    assert "camelot" in engine_ids
    pdfplumber = next(e for e in data["engines"] if e["id"] == "pdfplumber")
    assert pdfplumber["flavors"] == ["auto", "bordered", "unbordered"]


def test_lite_result_schema_keys():
    now = datetime.now(timezone.utc)
    result = LiteResult(
        job_id=str(uuid4()),
        status=JobStatus.SUCCEEDED,
        created_at=now,
        completed_at=now,
    )
    dumped = result.model_dump(mode="json")
    assert set(dumped.keys()) == LITE_RESULT_TOP_KEYS
    assert dumped["schema_version"] == LITE_SCHEMA_VERSION
    assert dumped["api_version"] == LITE_API_VERSION


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "docuvision-lite"
