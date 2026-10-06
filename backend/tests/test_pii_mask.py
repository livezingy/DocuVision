"""P-030a PII mask contract: three-variant masking, scope exclusions, step wiring.

Pure logic (mock, no paddle/server). Step tests follow the
test_orchestrator_order.py stub pattern.
"""

import asyncio
import copy

import fitz

from app.orchestration.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator,
    finalize_step,
    pii_mask_step,
)
from app.services.pii_mask import MASK_TOKEN, mask_result_exit, mask_text


def make_orchestrator(services):
    async def noop_update_progress(ctx, progress, message):
        return None

    async def call_maybe_async(func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    def is_cancelled(task_id):
        return False

    def build_page_image_meta(file_path, task_id=None, page_num=1):
        return {"width_px": 1000, "height_px": 1000}

    return DocumentPipelineOrchestrator(
        services=services,
        send_event=lambda *a, **k: asyncio.sleep(0),
        is_cancelled=is_cancelled,
        call_maybe_async=call_maybe_async,
        build_page_image_meta=build_page_image_meta,
    )


def make_ctx(task, result):
    return {
        "task_id": "t-pii",
        "task": task,
        "file_path": task["file_path"],
        "options": task.get("options", {}),
        "result": result,
        "orchestrator": make_orchestrator({}),
        "start_time": None,
    }


# --- X2: three variants hit, non-variant forms untouched -------------------


def test_three_variants_masked():
    for raw in ("123-45-6789", "12-3456789", "123456789"):
        masked, n = mask_text(raw)
        assert masked == MASK_TOKEN, raw
        assert n == 1, raw


def test_mixed_text_masked_with_count():
    masked, n = mask_text("EIN 12-3456789 and SSN 123-45-6789 and ref 987654321")
    assert masked == f"EIN {MASK_TOKEN} and SSN {MASK_TOKEN} and ref {MASK_TOKEN}"
    assert n == 3


def test_non_variant_forms_untouched():
    untouched = [
        "12345678",  # 8 digits
        "1234567890",  # 10 digits
        "12345678901",  # 11 digits
        "A123456789",  # letter-adjacent run (not a bare digit word)
        "2026-10-06",  # date-shaped
        "INV-2024-001",  # short groups
        "no digits here",
        "",
    ]
    for raw in untouched:
        masked, n = mask_text(raw)
        assert masked == raw, raw
        assert n == 0, raw


# --- X2/X3: tree masking (in place, counted, scope exclusions) -------------


def test_mask_result_exit_mutates_in_place_and_counts():
    tax_id = "12-3456789"
    result = {
        "kie_fields": {"seller_tax_id": tax_id, "total": "$100.00"},
        "kie_fields_by_page": {"1": {"buyer_tax_id": "123-45-6789"}},
        "table_backfill": {"cells": [{"text": "987654321"}]},
    }
    snapshot = copy.deepcopy(result)
    kie_fields_ref = result["kie_fields"]

    count = mask_result_exit(result)

    assert count == 3
    assert result["kie_fields"]["seller_tax_id"] == MASK_TOKEN
    assert result["kie_fields"]["total"] == "$100.00"
    assert result["kie_fields_by_page"]["1"]["buyer_tax_id"] == MASK_TOKEN
    assert result["table_backfill"]["cells"][0]["text"] == MASK_TOKEN
    assert result["kie_fields"] is kie_fields_ref  # in place, not rebound
    assert result != snapshot


def test_evidence_and_document_info_excluded():
    result = {
        "document_info": {"file_name": "123456789.pdf"},
        "evidence": {"quotes": [{"quote": "SSN 123-45-6789 on file"}]},
        "kie_fields": {"seller_tax_id": "123456789"},
    }
    count = mask_result_exit(result)
    assert count == 1
    assert result["evidence"]["quotes"][0]["quote"] == "SSN 123-45-6789 on file"
    assert result["document_info"]["file_name"] == "123456789.pdf"
    assert result["kie_fields"]["seller_tax_id"] == MASK_TOKEN


def test_view_fields_shared_reference_receives_mask():
    # Orchestrator: view["fields"] = ctx["result"]["kie_fields"] (same object).
    kie_fields = {"seller_tax_id": "123-45-6789"}
    view = {"fields": kie_fields}
    result = {"kie_fields": kie_fields}

    mask_result_exit(result)

    assert view["fields"]["seller_tax_id"] == MASK_TOKEN


# --- Step wiring: default off = zero behavior (X4); mask before persist ----


def test_pii_mask_step_disabled_is_zero_behavior():
    tax_id = "12-3456789"
    result = {
        "document_info": {"file_name": "doc.pdf"},
        "kie_fields": {"seller_tax_id": tax_id},
        "evidence": {"verdict": "ok", "quote": tax_id},
    }
    snapshot = copy.deepcopy(result)
    task = {"file_path": "doc.pdf", "options": {}}

    asyncio.run(pii_mask_step(make_ctx(task, result)))

    assert result == snapshot  # byte-identical when off


def test_pii_mask_step_enabled_masks_and_logs_count_only():
    import io

    from loguru import logger

    tax_id = "12-3456789"
    result = {
        "kie_fields": {"seller_tax_id": tax_id},
        "evidence": {"quote": tax_id},
    }
    task = {"file_path": "doc.pdf", "options": {"enable_pii_mask": True}}

    buf = io.StringIO()
    handler_id = logger.add(buf, level="INFO")
    try:
        asyncio.run(pii_mask_step(make_ctx(task, result)))
    finally:
        logger.remove(handler_id)
    log_text = buf.getvalue()

    assert result["kie_fields"]["seller_tax_id"] == MASK_TOKEN
    assert result["evidence"]["quote"] == tax_id  # exempt subtree untouched
    assert "masked_values=1" in log_text
    assert tax_id not in log_text  # X3: 记计数不泄值


def test_mask_lands_before_finalize_persist(tmp_path, monkeypatch):
    doc = fitz.open()
    doc.new_page()
    pdf_path = tmp_path / "doc.pdf"
    doc.save(str(pdf_path))
    doc.close()

    persisted = {}
    from app.services.persistence import analyze_job_store

    async def fake_persist(task):
        persisted.update(task)
        return None

    monkeypatch.setattr(analyze_job_store, "persist_task_safe", fake_persist)

    result = {
        "document_info": {"page_image_meta": {}},
        "kie_fields": {"seller_tax_id": "123456789"},
    }
    task = {
        "file_path": str(pdf_path),
        "file_name": "doc.pdf",
        "status": "running",
        "options": {"enable_pii_mask": True},
    }
    ctx = make_ctx(task, result)

    asyncio.run(pii_mask_step(ctx))
    asyncio.run(finalize_step(ctx))

    assert persisted["result"]["kie_fields"]["seller_tax_id"] == MASK_TOKEN
    assert ctx["task"]["result"]["kie_fields"]["seller_tax_id"] == MASK_TOKEN
