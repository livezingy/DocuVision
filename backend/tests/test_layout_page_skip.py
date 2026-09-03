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
