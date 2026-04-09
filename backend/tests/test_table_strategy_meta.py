"""Table strategy metadata tests.

These tests validate layout-first policy metadata without requiring Paddle models.
"""

from typing import Any, Dict, List
import importlib.util
from pathlib import Path
import asyncio

import pytest


_TABLE_SERVICE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "table_service.py"
_SPEC = importlib.util.spec_from_file_location("table_service_for_tests", _TABLE_SERVICE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load table_service module from {_TABLE_SERVICE_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
TableService = _MODULE.TableService


def test_extract_with_meta_layout_first_success() -> None:
    service = TableService(use_gpu=False, allow_fullpage_fallback=False)

    async def fake_extract_internal(**kwargs: Any):
        tables: List[Dict[str, Any]] = [{"id": "t1"}, {"id": "t2"}]
        meta: Dict[str, Any] = {
            "strategy": "layout_first",
            "engine_requested": "ppstructure",
            "allow_fullpage_fallback": False,
            "layout_elements": 8,
            "layout_table_blocks": 2,
            "path": "layout_first",
            "reason": "layout_tables_consumed",
            "fallback_activated": False,
            "engine_used": "ppstructure",
            "tables_returned": 2,
        }
        return tables, meta

    service._extract_internal = fake_extract_internal  # type: ignore[attr-defined]

    wrapped = asyncio.run(
        service.extract_with_meta(
            file_path="dummy.png",
            layout_elements=[{"type": "table"}, {"type": "table"}],
            allow_fullpage_fallback=False,
        )
    )

    assert isinstance(wrapped, dict)
    assert wrapped["tables"] == [{"id": "t1"}, {"id": "t2"}]
    assert wrapped["meta"]["path"] == "layout_first"
    assert wrapped["meta"]["fallback_activated"] is False
    assert wrapped["meta"]["tables_returned"] == 2


def test_extract_with_meta_skipped_when_fallback_disabled() -> None:
    service = TableService(use_gpu=False, allow_fullpage_fallback=False)

    async def fake_extract_internal(**kwargs: Any):
        return [], {
            "strategy": "layout_first",
            "engine_requested": "ppstructure",
            "allow_fullpage_fallback": False,
            "layout_elements": 0,
            "layout_table_blocks": 0,
            "path": "skipped",
            "reason": "missing_layout_input_fallback_disabled",
            "fallback_activated": False,
            "engine_used": None,
            "tables_returned": 0,
        }

    service._extract_internal = fake_extract_internal  # type: ignore[attr-defined]

    wrapped = asyncio.run(
        service.extract_with_meta(
            file_path="dummy.png",
            layout_elements=None,
            allow_fullpage_fallback=False,
        )
    )

    assert wrapped["tables"] == []
    assert wrapped["meta"]["path"] == "skipped"
    assert wrapped["meta"]["reason"] == "missing_layout_input_fallback_disabled"


def test_get_strategy_info_defaults() -> None:
    service = TableService(use_gpu=False, allow_fullpage_fallback=False)
    info = service.get_strategy_info()

    assert info["mode"] == "layout_first"
    assert info["allow_fullpage_fallback"] is False
    assert info["default_engine"] == "ppstructure"
    assert "ppstructure" in info["available_engines"]
