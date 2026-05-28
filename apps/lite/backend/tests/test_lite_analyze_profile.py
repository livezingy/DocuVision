"""Integration tests for Lite analyze/profile route."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.skipif(not (FIXTURES / "sample_bordered.pdf").exists(), reason="sample PDF missing")
def test_analyze_profile_digital_pdf():
    pdf_path = FIXTURES / "sample_bordered.pdf"
    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/v1/lite/analyze/profile",
            files={"file": ("sample_bordered.pdf", f, "application/pdf")},
        )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["input"]["detected_file_type"] == "pdf_digital"
    assert len(data["pages"]) >= 1
    assert data["pages"][0]["table_type"] in ("bordered", "unbordered", "none")
    assert data["pages"][0]["suggested_routing"]["flavor"] in ("bordered", "unbordered")
    assert data["scan_profile"] is None


def test_analyze_profile_file_too_large(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "MAX_FILE_SIZE_MB", 1)
    huge = b"0" * (2 * 1024 * 1024)
    response = client.post(
        "/api/v1/lite/analyze/profile",
        files={"file": ("big.pdf", huge, "application/pdf")},
    )
    assert response.status_code == 413


def test_analyze_profile_png_scan():
    png_path = FIXTURES / "sample.png"
    if not png_path.exists():
        # minimal 1x1 PNG
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
            b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        response = client.post(
            "/api/v1/lite/analyze/profile",
            files={"file": ("sample.png", png_bytes, "image/png")},
        )
    else:
        with png_path.open("rb") as f:
            response = client.post(
                "/api/v1/lite/analyze/profile",
                files={"file": ("sample.png", f, "image/png")},
            )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["input"]["detected_file_type"] == "image"
    assert data["pages"] == []
    assert data["scan_profile"] is not None
    assert data["scan_profile"]["message"]
