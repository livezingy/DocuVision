"""Bordered digital PDF table extraction (Smart mode)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.skipif(not (FIXTURES / "sample_bordered.pdf").exists(), reason="sample PDF missing")
def test_extract_auto_bordered_pdf_returns_tables():
    pdf_path = FIXTURES / "sample_bordered.pdf"
    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/v1/lite/extract/auto",
            files={"file": ("sample_bordered.pdf", f, "application/pdf")},
            data={"mode": "smart", "score_threshold": "0.5"},
        )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["quality"]["tables_found"] >= 1, data
    assert len(data["tables"]) >= 1
    first = data["tables"][0]
    assert first.get("row_count", 0) >= 1
    assert first.get("col_count", 0) >= 1


@pytest.mark.skipif(not (FIXTURES / "sample_bordered.pdf").exists(), reason="sample PDF missing")
def test_analyze_profile_bordered_type():
    pdf_path = FIXTURES / "sample_bordered.pdf"
    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/v1/lite/analyze/profile",
            files={"file": ("sample_bordered.pdf", f, "application/pdf")},
        )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["pages"][0]["table_type"] in ("bordered", "unbordered")
