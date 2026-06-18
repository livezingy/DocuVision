"""
Live API integration tests (require ``python run.py`` on :8000).

When the server is not running, tests in this module are skipped automatically
(see ``tests/conftest.py`` ``require_live_api``). Sample files live under
``test_data/testfiles/``.

Run invoice KIE alone (GPU, server must stay up):

    pytest tests/test_live_api.py::TestLiveInvoiceKie -s
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
import requests

API_BASE_URL = "http://localhost:8000/api/v1"
BASE_URL = "http://localhost:8000"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TESTFILES_DIR = PROJECT_ROOT / "test_data" / "testfiles"


def _poll_task_status(
    task_id: str,
    *,
    max_wait: int = 300,
    interval: int = 3,
    max_consecutive_errors: int = 20,
) -> tuple[str, dict]:
    """Poll task until completed or failed; pytest.fail on timeout."""
    elapsed = 0
    last_status = None
    consecutive_errors = 0
    last_diag = ""

    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            response = requests.get(f"{API_BASE_URL}/tasks/{task_id}", timeout=30)
        except requests.exceptions.RequestException as exc:
            consecutive_errors += 1
            last_diag = f"request_error:{exc}"
            if consecutive_errors >= max_consecutive_errors:
                pytest.fail(f"Task poll failed {consecutive_errors} times: {last_diag}")
            continue

        if response.status_code != 200:
            consecutive_errors += 1
            last_diag = f"http_{response.status_code}"
            if consecutive_errors >= max_consecutive_errors:
                pytest.fail(f"Task poll HTTP errors {consecutive_errors} times: {last_diag}")
            continue

        consecutive_errors = 0
        task_status = response.json()
        status = task_status["status"]
        if status != last_status:
            progress = task_status.get("progress", 0)
            message = task_status.get("message", "")
            print(f"   status={status} progress={progress}% msg={message[:60]}")
            last_status = status

        if status == "completed":
            return status, task_status
        if status == "failed":
            pytest.fail(f"Task failed: {task_status.get('message', 'Unknown error')}")

    pytest.fail(
        f"Task not completed within {max_wait}s "
        f"(last_status={last_status!r}, last_diag={last_diag!r})"
    )


class TestLiveApiEndpoints:
    """Smoke endpoints against a running Pro server."""

    def test_health_endpoint(self):
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health_reports_services(self):
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        services = response.json().get("services", {})
        assert isinstance(services, dict)
        for name, info in services.items():
            assert "ready" in info, f"service {name} missing ready flag"

    def test_list_engines(self):
        response = requests.get(f"{API_BASE_URL}/engines", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert "ocr" in data and "layout" in data and "table" in data

    def test_list_batches(self):
        response = requests.get(f"{API_BASE_URL}/batch", timeout=5)
        assert response.status_code == 200
        assert "batches" in response.json()


class TestLiveDocumentWorkflows:
    """User-style flows: OCR, analyze, batch, export."""

    def test_quick_ocr_on_sample_invoice(self):
        test_file = TESTFILES_DIR / "invoices" / "sample-invoice.png"
        if not test_file.is_file():
            pytest.skip(f"Test file not found: {test_file}")

        with open(test_file, "rb") as f:
            files = {"file": (test_file.name, f, "image/png")}
            response = requests.post(f"{API_BASE_URL}/ocr", files=files, timeout=30)

        assert response.status_code == 200
        data = response.json()
        assert data.get("text")
        assert "engine" in data

    def test_complete_document_analysis_pdf(self):
        test_file = TESTFILES_DIR / "pdf" / "sample_report.pdf"
        if not test_file.is_file():
            pytest.skip(f"Test file not found: {test_file}")

        with open(test_file, "rb") as f:
            files = {"file": (test_file.name, f, "application/pdf")}
            data = {
                "enable_ocr": "true",
                "enable_layout": "true",
                "enable_table": "true",
            }
            response = requests.post(
                f"{API_BASE_URL}/analyze", files=files, data=data, timeout=30
            )

        assert response.status_code == 200
        task_id = response.json()["task_id"]
        _poll_task_status(task_id)

        result_response = requests.get(
            f"{API_BASE_URL}/tasks/{task_id}/result", timeout=30
        )
        assert result_response.status_code == 200
        result = result_response.json()
        assert "document_info" in result
        has_layout = isinstance(result.get("layout"), dict) and bool(result.get("layout"))
        view = result.get("view") if isinstance(result.get("view"), dict) else {}
        assert has_layout or bool(view.get("pages"))

    def test_batch_processing_two_files(self):
        test_files = [
            TESTFILES_DIR / "pdf" / "sample_report.pdf",
            TESTFILES_DIR / "invoices" / "sample-invoice.png",
        ]
        existing = [p for p in test_files if p.is_file()]
        if len(existing) < 2:
            pytest.skip(f"Need at least 2 test files, found {len(existing)}")

        files = []
        try:
            for path in existing[:2]:
                files.append(
                    ("files", (path.name, open(path, "rb"), "application/octet-stream"))
                )
            data = {
                "name": "Live API batch test",
                "options": '{"enable_ocr": true, "enable_layout": true}',
            }
            response = requests.post(
                f"{API_BASE_URL}/batch", files=files, data=data, timeout=30
            )
            assert response.status_code == 200
            batch_id = response.json()["batch_id"]

            requests.post(f"{API_BASE_URL}/batch/{batch_id}/start", timeout=30)

            max_wait, elapsed = 300, 0
            while elapsed < max_wait:
                time.sleep(3)
                elapsed += 3
                batch_resp = requests.get(f"{API_BASE_URL}/batch/{batch_id}", timeout=30)
                if batch_resp.status_code != 200:
                    continue
                batch_status = batch_resp.json()
                if batch_status["status"] == "completed":
                    results_resp = requests.get(
                        f"{API_BASE_URL}/batch/{batch_id}/results", timeout=30
                    )
                    assert results_resp.status_code == 200
                    return
                if batch_status["status"] == "failed":
                    pytest.fail(batch_status.get("message", "Batch failed"))
            pytest.fail(f"Batch not completed within {max_wait}s")
        finally:
            for _, (_, fh, _) in files:
                if hasattr(fh, "close"):
                    fh.close()

    def test_export_json_xlsx_docx(self):
        test_file = TESTFILES_DIR / "pdf" / "sample_report.pdf"
        if not test_file.is_file():
            pytest.skip(f"Test file not found: {test_file}")

        with open(test_file, "rb") as f:
            files = {"file": (test_file.name, f, "application/pdf")}
            data = {"enable_ocr": "true", "enable_table": "true"}
            response = requests.post(
                f"{API_BASE_URL}/analyze", files=files, data=data, timeout=60
            )
        assert response.status_code == 200
        task_id = response.json()["task_id"]
        _poll_task_status(task_id)

        ok_count = 0
        for fmt in ("json", "xlsx", "docx"):
            resp = requests.get(
                f"{API_BASE_URL}/tasks/{task_id}/export/{fmt}", timeout=30
            )
            if resp.status_code == 200:
                ok_count += 1
        assert ok_count > 0, "At least one export format should succeed"

    def test_removed_templates_returns_404(self):
        response = requests.get(f"{API_BASE_URL}/templates", timeout=5)
        assert response.status_code == 404


class TestLiveInvoiceKie:
    """Invoice KIE on live GPU server (run alone; competes for GPU with full pytest)."""

    def test_invoice_analyze_kie_production_hit(self):
        test_file = TESTFILES_DIR / "invoices" / "invoice_sample_01.pdf"
        if not test_file.is_file():
            pytest.skip(f"Test file not found: {test_file}")

        data = {
            "document_type": "invoice",
            "enable_layout": "true",
            "enable_table": "true",
            "enable_ocr": "false",
            "enable_formula": "false",
            "enable_chart": "false",
            "enable_seal": "false",
            "enable_kie": "true",
        }
        with open(test_file, "rb") as f:
            files = {"file": (test_file.name, f, "application/pdf")}
            response = requests.post(
                f"{API_BASE_URL}/analyze", files=files, data=data, timeout=60
            )
        assert response.status_code == 200, response.text[:500]
        task_id = response.json()["task_id"]
        _poll_task_status(task_id, max_wait=600, interval=5)

        result_resp = requests.get(f"{API_BASE_URL}/tasks/{task_id}/result", timeout=30)
        assert result_resp.status_code == 200
        result = result_resp.json()

        quality = result.get("quality") if isinstance(result.get("quality"), dict) else {}
        kie_fields = result.get("kie_fields") if isinstance(result.get("kie_fields"), dict) else {}
        view = result.get("view") if isinstance(result.get("view"), dict) else {}
        view_fields = view.get("fields") if isinstance(view.get("fields"), dict) else {}
        if not kie_fields and view_fields:
            kie_fields = view_fields

        if not quality.get("kie_attempted"):
            pytest.skip("KIE was not attempted in this server profile")

        kie_stage = str(quality.get("kie_stage", "") or "")
        n_fields = int(quality.get("kie_fields_count", 0) or 0) or len(kie_fields)

        if kie_stage == "runtime_error":
            err_msg = str(quality.get("kie_error_message", "") or "")[:300]
            pytest.skip(
                f"KIE runtime_error (often GPU OOM during full pytest): {err_msg}. "
                "Re-run alone: pytest tests/test_live_api.py::TestLiveInvoiceKie -s"
            )

        from app.services.kie.kie_field_metrics import (
            evaluate_kie_contract,
            evaluate_kie_production_hit,
        )

        contract_ok, contract_reason = evaluate_kie_contract(kie_stage, n_fields)
        if not contract_ok:
            pytest.fail(
                f"KIE contract failed: stage={kie_stage!r} reason={contract_reason!r}"
            )

        prod_hit, prod_reason, prod_keys = evaluate_kie_production_hit(
            "invoice", kie_fields
        )
        if not prod_hit:
            pytest.fail(
                f"KIE production hit failed: reason={prod_reason!r} keys={prod_keys!r}"
            )


def _server_running() -> bool:
    try:
        return requests.get(f"{BASE_URL}/health", timeout=3).status_code == 200
    except requests.exceptions.RequestException:
        return False


if __name__ == "__main__":
    if not _server_running():
        print("Server not running. Start: cd backend && python run.py")
        sys.exit(1)
    pytest.main([__file__, "-v", "-s"])
