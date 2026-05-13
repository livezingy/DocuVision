"""KIE acceptance baseline tests for tracker item 1.

This file provides:
1) Fast unit-level contract tests for the selected KIE acceptance rule.
2) An optional in-process API smoke skeleton for cloud validation.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import pytest


_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
_PROJECT_ROOT = _BACKEND_DIR.parent

_SAMPLE_MATRIX = [
    _PROJECT_ROOT / "test_data" / "testfiles" / "templates" / "invoice" / "invoice_sample_01.pdf",
    _PROJECT_ROOT / "test_data" / "testfiles" / "templates" / "invoice" / "receipt-invoice-like.png",
    _PROJECT_ROOT / "test_data" / "testfiles" / "templates" / "invoice" / "sample-invoice.png",
]


def _evaluate_kie_acceptance(kie_stage: str, kie_fields_count: int) -> tuple[bool, str]:
    """Evaluate KIE acceptance based on the current baseline rule.

    Rule KIE-ACCEPT-001:
    - stage must be "completed"
    - fields_count can be zero or greater
    """
    if kie_stage != "completed":
        return False, f"stage_not_completed:{kie_stage}"

    if kie_fields_count < 0:
        return False, f"invalid_negative_count:{kie_fields_count}"

    if kie_fields_count == 0:
        return True, "completed_with_zero_fields_allowed"

    return True, "completed_with_field_hits"


def test_kie_invoice_sample_matrix_has_minimum_samples() -> None:
    existing = [p for p in _SAMPLE_MATRIX if p.exists()]
    assert len(existing) >= 3, f"Need >=3 invoice samples, found {len(existing)}"


def test_kie_acceptance_rule_allows_zero_fields_when_completed() -> None:
    accepted, reason = _evaluate_kie_acceptance("completed", 0)
    assert accepted is True
    assert reason == "completed_with_zero_fields_allowed"


def test_kie_acceptance_rule_rejects_non_completed_stage() -> None:
    accepted, reason = _evaluate_kie_acceptance("runtime_error", 0)
    assert accepted is False
    assert reason.startswith("stage_not_completed")


@pytest.mark.skipif(
    os.getenv("DOCUVISION_RUN_KIE_ACCEPTANCE") != "1",
    reason="Set DOCUVISION_RUN_KIE_ACCEPTANCE=1 to enable heavy KIE smoke validation",
)
def test_kie_invoice_documents_analyze_smoke_contract() -> None:
    """Optional cloud smoke: run KIE through /api/v1/documents:analyze.

    This is intentionally opt-in because it can be heavy and model-dependent.
    """

    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed")

    if str(_BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(_BACKEND_DIR))

    try:
        from app.main import app  # noqa: PLC0415
    except Exception as exc:
        pytest.skip(f"Unable to import app.main: {exc}")

    async def _run() -> None:
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=120) as client:
            for sample in _SAMPLE_MATRIX:
                if not sample.exists():
                    pytest.skip(f"Missing sample: {sample}")

                ext = sample.suffix.lower().lstrip(".")
                mime = "application/pdf" if ext == "pdf" else f"image/{ext}"

                with open(sample, "rb") as fh:
                    resp = await client.post(
                        "/api/v1/documents:analyze",
                        files={"file": (sample.name, fh, mime)},
                        data={
                            "enable_kie": "true",
                            "document_type": "invoice",
                            "return_raw": "false",
                        },
                    )

                assert resp.status_code == 200, f"submit failed for {sample.name}: {resp.text[:200]}"
                job_id = resp.json().get("job_id")
                assert job_id, f"missing job_id for {sample.name}"

                final_status = "running"
                for _ in range(240):
                    st = await client.get(f"/api/v1/jobs/{job_id}")
                    assert st.status_code == 200, f"status failed for {sample.name}: {st.text[:200]}"
                    final_status = st.json().get("status", "unknown")
                    if final_status in ("succeeded", "completed", "failed"):
                        break
                    await asyncio.sleep(1)

                assert final_status in ("succeeded", "completed"), (
                    f"job did not complete for {sample.name}: {final_status}"
                )

                result = await client.get(f"/api/v1/jobs/{job_id}/result")
                assert result.status_code == 200, f"result failed for {sample.name}: {result.text[:200]}"

                body = result.json()
                quality = body.get("quality", {}) if isinstance(body.get("quality"), dict) else {}
                kie_stage = str(quality.get("kie_stage", ""))
                kie_fields_count = int(quality.get("kie_fields_count", 0) or 0)

                accepted, reason = _evaluate_kie_acceptance(kie_stage, kie_fields_count)
                assert accepted, (
                    f"acceptance failed for {sample.name}: stage={kie_stage}, "
                    f"fields={kie_fields_count}, reason={reason}"
                )

    t0 = time.time()
    asyncio.run(_run())
    assert (time.time() - t0) >= 0
