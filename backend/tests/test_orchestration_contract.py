"""
Contract tests for orchestrator split and API route exposure.
These tests intentionally describe target architecture and should fail
until the refactor is implemented.
"""

from __future__ import annotations

import sys
from pathlib import Path


_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def test_orchestrator_module_contract():
    """Orchestrator module must expose standard step entry points."""
    from app.orchestration import document_pipeline_orchestrator as orchestrator

    assert hasattr(orchestrator, "DocumentPipelineOrchestrator")
    assert hasattr(orchestrator, "ocr_step")
    assert hasattr(orchestrator, "layout_step")
    assert hasattr(orchestrator, "table_step")
    assert hasattr(orchestrator, "nlp_step")
    assert hasattr(orchestrator, "template_step")
    assert hasattr(orchestrator, "finalize_step")


def test_task_routes_include_layout_and_blocks_endpoints():
    """Task API must expose both layout and flat blocks endpoints."""
    main_path = _BACKEND_DIR / "app" / "main.py"
    source = main_path.read_text(encoding="utf-8")

    has_layout = '@app.get("/api/v1/tasks/{task_id}/layout")' in source
    has_blocks = '@app.get("/api/v1/tasks/{task_id}/blocks")' in source

    assert has_layout, "Missing GET /api/v1/tasks/{task_id}/layout"
    assert has_blocks, "Missing GET /api/v1/tasks/{task_id}/blocks"
