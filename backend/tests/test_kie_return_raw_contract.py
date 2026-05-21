"""KIE and return_raw contract tests for pipeline orchestrator.

These tests validate option-to-output closure without requiring Paddle models.
"""

from pathlib import Path
import importlib.util
import asyncio
from datetime import datetime


_ORCH_PATH = Path(__file__).resolve().parents[1] / "app" / "orchestration" / "document_pipeline_orchestrator.py"
_SPEC = importlib.util.spec_from_file_location("orchestrator_for_tests", _ORCH_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load orchestrator module from {_ORCH_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
kie_step = _MODULE.kie_step
phase1_envelope_step = _MODULE.phase1_envelope_step


class _FakeOrchestrator:
    def ensure_not_cancelled(self, ctx):
        return None

    async def update_progress(self, ctx, progress, message):
        ctx.setdefault("_progress_log", []).append((progress, message))


def test_kie_step_populates_placeholder_meta() -> None:
    ctx = {
        "options": {"enable_kie": True, "document_type": "invoice"},
        "result": {},
        "orchestrator": _FakeOrchestrator(),
    }

    asyncio.run(kie_step(ctx))

    assert ctx["result"]["kie_fields"] == {}
    assert ctx["result"]["kie_meta"]["attempted"] is True
    assert ctx["result"]["kie_meta"]["stage"] == "service_unavailable"
    assert ctx["result"]["kie_meta"]["error_code"] == "service_unavailable"


def test_kie_step_calls_service_and_sets_fields() -> None:
    class _MockKieService:
        async def extract_fields(self, file_path: str, document_type: str):
            assert file_path == "dummy.png"
            assert document_type == "invoice"
            return {"document_type": document_type, "fields": {"invoice_no": {"value": "INV-001"}}}

    async def call_maybe_async(func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    orch = _FakeOrchestrator()
    orch.services = {"kie_service": _MockKieService()}
    orch.call_maybe_async = call_maybe_async

    ctx = {
        "options": {"enable_kie": True, "document_type": "invoice"},
        "result": {},
        "orchestrator": orch,
        "file_path": "dummy.png",
    }

    asyncio.run(kie_step(ctx))

    assert ctx["result"]["kie_meta"]["succeeded"] is True
    assert ctx["result"]["kie_meta"]["stage"] == "completed"
    assert ctx["result"]["kie_fields"]["invoice_no"]["value"] == "INV-001"


def test_phase1_envelope_respects_return_raw_false() -> None:
    ctx = {
        "task_id": "job_test",
        "task": {"preprocessed_image_path": None},
        "file_path": "dummy.png",
        "options": {"return_raw": False},
        "result": {
            "layout": {
                "elements": [],
                "input_size": {"width": 100, "height": 100},
                "output_size": {"width": 100, "height": 100},
                "use_doc_orientation_classify": False,
                "angle_deg": 0.0,
            },
            "kie_fields": {"invoice_no": {"value": "INV-001"}},
            "kie_meta": {
                "attempted": True,
                "stage": "completed",
                "error_code": "",
            },
        },
        "orchestrator": _FakeOrchestrator(),
        "start_time": datetime.now(),
    }

    asyncio.run(phase1_envelope_step(ctx))

    envelope = ctx["task"]["envelope"]
    assert envelope["raw"] == {}
    assert envelope["view"]["fields"]["invoice_no"]["value"] == "INV-001"
    assert envelope["quality"]["kie_attempted"] is True
    assert envelope["quality"]["kie_error_code"] == ""
    assert envelope["quality"]["kie_fields_count"] == 1
