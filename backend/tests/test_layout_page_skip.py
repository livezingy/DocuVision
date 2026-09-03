"""Page-by-page layout worker dispatch tests (no Paddle/GPU).

Locks two bugs found in Cloud validation of 03_paper_arxiv-mamba:

1. Worker called ``asyncio.run`` on sync ``_analyze_image_layout_only``
   (and originally had no ``import asyncio``), so every page failed instantly
   with NameError / ValueError. Official: asyncio.run requires a coroutine
   https://docs.python.org/3.11/library/asyncio-runner.html#asyncio.run
2. ``total_pages`` used ``len(page_layouts)`` (successes), so a full skip
   reported ``total_pages=0``.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

for _mod in ("paddle", "cv2"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

_LAYOUT_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "layout_service.py"
_spec = importlib.util.spec_from_file_location("layout_service_for_page_skip_tests", _LAYOUT_PATH)
assert _spec is not None and _spec.loader is not None
_layout_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_layout_mod)

_invoke_worker_command = _layout_mod._invoke_worker_command
_build_pdf_layout_result = _layout_mod._build_pdf_layout_result
_truncate_error = _layout_mod._truncate_error


class _FakeEngine:
    def __init__(self) -> None:
        self.layout_only_calls = 0
        self.image_calls = 0

    def _analyze_image_layout_only(self, file_path: str):
        self.layout_only_calls += 1
        return {
            "elements": [{"id": "e1", "type": "text", "page": 1}],
            "page_layout": {"text": 1},
            "path": file_path,
        }

    async def _analyze_image(self, file_path: str):
        self.image_calls += 1
        return {"elements": [], "path": file_path}

    async def _analyze_pdf(self, file_path: str):
        return {"elements": [], "path": file_path, "total_pages": 2}


def test_analyze_image_layout_invokes_sync_method_not_asyncio_run() -> None:
    engine = _FakeEngine()
    result = _invoke_worker_command(engine, "analyze_image_layout", "page.png")
    assert engine.layout_only_calls == 1
    assert engine.image_calls == 0
    assert result["elements"][0]["id"] == "e1"


def test_analyze_image_still_drives_async_method() -> None:
    engine = _FakeEngine()
    result = _invoke_worker_command(engine, "analyze_image", "page.png")
    assert engine.image_calls == 1
    assert result["elements"] == []


def test_unknown_command_raises() -> None:
    engine = _FakeEngine()
    try:
        _invoke_worker_command(engine, "not_a_cmd", "page.png")
    except ValueError as exc:
        assert "Unknown" in str(exc)
    else:
        raise AssertionError("expected ValueError for unknown command")


def test_total_pages_is_pdf_count_when_all_pages_failed() -> None:
    result = _build_pdf_layout_result(
        page_count=36,
        all_elements=[],
        page_layouts=[],
        failed_pages=list(range(1, 37)),
        failed_page_errors=[{"page": 1, "error": "name 'asyncio' is not defined"}],
    )
    assert result["total_pages"] == 36
    assert result["elements"] == []
    assert result["failed_pages"] == list(range(1, 37))
    assert result["failed_page_errors"][0]["error"] == "name 'asyncio' is not defined"


def test_total_pages_counts_pdf_not_successes() -> None:
    result = _build_pdf_layout_result(
        page_count=3,
        all_elements=[{"type": "text"}],
        page_layouts=[{"page": 1}, {"page": 3}],
        failed_pages=[2],
    )
    assert result["total_pages"] == 3
    assert len(result["page_layouts"]) == 2
    assert result["failed_pages"] == [2]


def test_truncate_error_caps_length() -> None:
    assert _truncate_error("x" * 500, limit=10) == "xxxxxxxxxx..."
    assert _truncate_error("") == "unknown error"


# ---------------------------------------------------------------------------
# _call_engine must not pass predict kwargs (PaddleX issue #17446)
# ---------------------------------------------------------------------------

class _FakePPStructureV3:
    """Records predict call kwargs to verify no overrides are passed."""

    def __init__(self) -> None:
        self.predict_calls: list = []

    def predict(self, img_path: str, **kwargs):
        self.predict_calls.append((img_path, kwargs))
        return [{"parsing_res_list": [], "table_res_list": []}]


class _FakePPStructureEngine:
    """Minimal stand-in for PPStructureEngine exposing _call_engine."""

    def __init__(self, engine) -> None:
        self._engine = engine
        self._is_v3 = True

    def _save_visualization_outputs(self, result, vis_src_path):
        pass  # no-op for tests

    # Delegate to the real method on the module-level class.
    def _call_engine(self, img_path: str, vis_src_path=None):
        # Reuse the actual PPStructureEngine._call_engine via the module.
        return _layout_mod.PPStructureEngine._call_engine(self, img_path, vis_src_path)


def test_call_engine_does_not_pass_predict_kwargs() -> None:
    """Passing use_doc_orientation_classify=False at predict time triggers
    PaddleX issue #17446 (empty detections → 1D boxes → IndexError).
    The init-time use_doc_unwarping=False already covers that setting.
    """
    inner = _FakePPStructureV3()
    wrapper = _FakePPStructureEngine(inner)
    wrapper._call_engine("/tmp/page.png")
    assert len(inner.predict_calls) == 1
    img_path, kwargs = inner.predict_calls[0]
    assert img_path == "/tmp/page.png"
    assert kwargs == {}, f"predict must not receive overrides, got {kwargs}"
