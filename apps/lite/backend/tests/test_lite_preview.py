"""Contract tests for Lite server-side document preview API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
FIXTURES = Path(__file__).parent / "fixtures"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.mark.skipif(not (FIXTURES / "sample_bordered.pdf").exists(), reason="sample PDF missing")
def test_preview_pdf_upload_and_page_image():
    pdf_path = FIXTURES / "sample_bordered.pdf"
    with pdf_path.open("rb") as f:
        upload = client.post(
            "/api/v1/lite/preview",
            files={"file": ("sample_bordered.pdf", f, "application/pdf")},
        )
    assert upload.status_code == 200, upload.text
    body = upload.json()
    assert body["preview_id"]
    assert body["page_count"] >= 1
    assert body["file_name"] == "sample_bordered.pdf"

    page = client.get(f"/api/v1/lite/preview/{body['preview_id']}/page-image/1")
    assert page.status_code == 200, page.text
    assert page.headers["content-type"].startswith("image/")
    assert page.content.startswith(PNG_MAGIC)


def test_preview_png_page_image():
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload = client.post(
        "/api/v1/lite/preview",
        files={"file": ("tiny.png", png_bytes, "image/png")},
    )
    assert upload.status_code == 200, upload.text
    preview_id = upload.json()["preview_id"]
    page = client.get(f"/api/v1/lite/preview/{preview_id}/page-image/1")
    assert page.status_code == 200
    assert page.content == png_bytes


def test_preview_unknown_session_returns_404():
    response = client.get("/api/v1/lite/preview/missing-id/page-image/1")
    assert response.status_code == 404


def test_preview_page_out_of_range():
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload = client.post(
        "/api/v1/lite/preview",
        files={"file": ("tiny.png", png_bytes, "image/png")},
    )
    preview_id = upload.json()["preview_id"]
    bad_page = client.get(f"/api/v1/lite/preview/{preview_id}/page-image/2")
    assert bad_page.status_code == 400
