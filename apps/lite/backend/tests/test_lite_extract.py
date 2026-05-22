"""Integration tests for Lite extract routes."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.skipif(not (FIXTURES / "sample_bordered.pdf").exists(), reason="sample PDF missing")
def test_extract_auto_digital_pdf():
    pdf_path = FIXTURES / "sample_bordered.pdf"
    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/v1/lite/extract/auto",
            files={"file": ("sample_bordered.pdf", f, "application/pdf")},
            data={"mode": "smart"},
        )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["input"]["detected_file_type"] == "pdf_digital"


def test_extract_file_too_large(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "MAX_FILE_SIZE_MB", 1)
    huge = b"0" * (2 * 1024 * 1024)
    response = client.post(
        "/api/v1/lite/extract/auto",
        files={"file": ("big.pdf", huge, "application/pdf")},
        data={"mode": "smart"},
    )
    assert response.status_code == 413


def test_create_async_job():
    pdf_path = FIXTURES / "sample_bordered.pdf"
    if not pdf_path.exists():
        pytest.skip("sample PDF missing")
    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/v1/lite/jobs",
            files={"file": ("sample_bordered.pdf", f, "application/pdf")},
            data={"mode": "smart"},
        )
    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "pending"
