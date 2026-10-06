import io
from fastapi.testclient import TestClient

from app.main import app
from app.core.runtime import tasks


client = TestClient(app)


def make_file_bytes():
    # Minimal PNG header bytes to satisfy file type checks
    return io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")


def test_analyze_auto_enable_kie_for_invoice():
    files = {"file": ("sample-invoice.png", make_file_bytes(), "image/png")}
    data = {"document_type": "invoice"}

    resp = client.post("/api/v1/analyze", files=files, data=data)
    assert resp.status_code == 200
    body = resp.json()
    task_id = body.get("task_id")
    assert task_id in tasks
    opts = tasks[task_id]["options"]
    # Backend fallback should enable KIE for invoice
    assert opts.get("document_type") == "invoice"
    assert opts.get("enable_kie") is True


def test_analyze_explicit_pico_accepted_with_kie_enabled():
    # P-031 X4 API arm: explicit pico passes through verbatim. The backend
    # fallback set intentionally does not auto-enable pico (coi precedent);
    # callers pass enable_kie explicitly, the frontend derives it from
    # KIE_DOC_TYPES.
    files = {"file": ("sample-pico.png", make_file_bytes(), "image/png")}
    data = {"document_type": "pico", "enable_kie": "1"}

    resp = client.post("/api/v1/analyze", files=files, data=data)
    assert resp.status_code == 200
    body = resp.json()
    task_id = body.get("task_id")
    assert task_id in tasks
    opts = tasks[task_id]["options"]
    assert opts.get("document_type") == "pico"
    assert opts.get("enable_kie") is True


def test_analyze_respects_explicit_disable_kie():
    files = {"file": ("sample-auto.png", make_file_bytes(), "image/png")}
    data = {"document_type": "auto", "enable_kie": "0"}

    resp = client.post("/api/v1/analyze", files=files, data=data)
    assert resp.status_code == 200
    body = resp.json()
    task_id = body.get("task_id")
    assert task_id in tasks
    opts = tasks[task_id]["options"]
    # When document_type is auto and client explicitly disables KIE, it should remain False
    assert opts.get("document_type") == "auto"
    assert opts.get("enable_kie") is False
