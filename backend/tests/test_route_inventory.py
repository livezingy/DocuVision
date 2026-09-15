"""Route inventory guard for the main.py split (v1.8.2, SPLIT-U2).

Static AST scan (no ``import app.main``) so this stays runnable locally without
the paddle stack. Works before and after the split: it reads both the legacy
``@app.<method>`` decorators (``main.py``) and the per-domain
``@router.<method>`` decorators (``backend/app/routers/*.py``).

The expected set is the frozen v1.8.1 route inventory (55 routes). Any added or
removed route must update this set *and* the full OpenAPI snapshot
(``test_openapi_snapshot_full.py``).
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = REPO_ROOT / "backend" / "app"
MAIN = APP_DIR / "main.py"
ROUTERS_DIR = APP_DIR / "routers"

_ROUTE_METHODS = {"get", "post", "put", "delete", "patch", "websocket"}

# Frozen v1.8.1 inventory: 55 (method, path) pairs.
EXPECTED_ROUTES: set[tuple[str, str]] = {
    # system
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/engines"),
    # analyzer
    ("POST", "/api/v1/ocr"),
    ("POST", "/api/v1/upload"),
    ("POST", "/api/v1/analyze"),
    # documents
    ("POST", "/api/v1/documents:analyze"),
    ("POST", "/api/v1/document/profile"),
    # jobs
    ("GET", "/api/v1/jobs/{job_id}"),
    ("GET", "/api/v1/jobs/{job_id}/result"),
    ("GET", "/api/v1/jobs/{job_id}/debug"),
    ("GET", "/api/v1/jobs/{job_id}/debug/{filename}"),
    # tasks (lifecycle)
    ("GET", "/api/v1/tasks/{task_id}"),
    ("GET", "/api/v1/tasks/{task_id}/events"),
    ("WS", "/api/v1/tasks/{task_id}/ws"),
    ("POST", "/api/v1/tasks/{task_id}/cancel"),
    ("PATCH", "/api/v1/tasks/{task_id}/kie-fields"),
    ("DELETE", "/api/v1/tasks/{task_id}"),
    # tasks (content)
    ("GET", "/api/v1/tasks/{task_id}/result"),
    ("GET", "/api/v1/tasks/{task_id}/layout"),
    ("GET", "/api/v1/tasks/{task_id}/blocks"),
    ("GET", "/api/v1/tasks/{task_id}/figures"),
    ("GET", "/api/v1/tasks/{task_id}/figures/{figure_id}"),
    ("GET", "/api/v1/tasks/{task_id}/page-image/{page_num}"),
    ("GET", "/api/v1/tasks/{task_id}/export/{format}"),
    # trial
    ("POST", "/api/v1/trial/gt-diff/{task_id}"),
    ("GET", "/api/v1/trial/gt-diff/{task_id}/report"),
    # batch (management)
    ("POST", "/api/v1/batch"),
    ("GET", "/api/v1/batch"),
    ("GET", "/api/v1/batch/{batch_id}"),
    ("POST", "/api/v1/batch/{batch_id}/start"),
    ("POST", "/api/v1/batch/{batch_id}/pause"),
    ("POST", "/api/v1/batch/{batch_id}/resume"),
    ("POST", "/api/v1/batch/{batch_id}/cancel"),
    ("DELETE", "/api/v1/batch/{batch_id}"),
    ("POST", "/api/v1/batch/{batch_id}/retry"),
    # batch (export)
    ("GET", "/api/v1/batch/{batch_id}/summary"),
    ("GET", "/api/v1/batch/{batch_id}/results"),
    ("GET", "/api/v1/batch/{batch_id}/export.csv"),
    ("GET", "/api/v1/batch/{batch_id}/export.xlsx"),
    ("GET", "/api/v1/batch/{batch_id}/export.json"),
    # kie
    ("GET", "/api/v1/kie/templates"),
    ("GET", "/api/v1/kie/templates/{template_id}"),
    ("POST", "/api/v1/kie/templates/{template_id}"),
    # hitl
    ("GET", "/api/v1/hitl/reviews"),
    ("GET", "/api/v1/hitl/reviews/{review_id}"),
    ("POST", "/api/v1/hitl/reviews/{review_id}/resolve"),
    # webhooks
    ("GET", "/api/v1/webhooks"),
    ("POST", "/api/v1/webhooks"),
    # pdf-tools
    ("POST", "/api/v1/pdf-tools/split"),
    ("POST", "/api/v1/pdf-tools/merge"),
    ("POST", "/api/v1/pdf-tools/metadata"),
    ("POST", "/api/v1/pdf-tools/searchable"),
    ("POST", "/api/v1/pdf-tools/form-fill"),
}

EXPECTED_COUNT = 55


def _route_from_decorator(dec: ast.AST) -> tuple[str, str] | None:
    """Return (METHOD, path) for an ``@app.<m>`` / ``@router.<m>`` decorator."""
    if not isinstance(dec, ast.Call):
        return None
    func = dec.func
    if not isinstance(func, ast.Attribute) or func.attr not in _ROUTE_METHODS:
        return None
    value = func.value
    if not (isinstance(value, ast.Name) and value.id in {"app", "router"}):
        return None
    if not dec.args:
        return None
    first = dec.args[0]
    if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
        return None
    method = "WS" if func.attr == "websocket" else func.attr.upper()
    return method, first.value


def _target_files() -> list[Path]:
    files = [MAIN]
    if ROUTERS_DIR.is_dir():
        files.extend(sorted(ROUTERS_DIR.rglob("*.py")))
    return files


def collect_routes() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in _target_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    route = _route_from_decorator(dec)
                    if route is not None:
                        found.append(route)
    return found


def test_route_inventory_count() -> None:
    found = collect_routes()
    assert len(found) == EXPECTED_COUNT, (
        f"expected {EXPECTED_COUNT} routes, found {len(found)}: {sorted(found)}"
    )


def test_route_inventory_no_duplicates() -> None:
    found = collect_routes()
    dupes = sorted({r for r in found if found.count(r) > 1})
    assert not dupes, f"duplicate route decorators: {dupes}"


def test_route_inventory_matches_frozen_set() -> None:
    routes = set(collect_routes())
    missing = sorted(EXPECTED_ROUTES - routes)
    unexpected = sorted(routes - EXPECTED_ROUTES)
    assert not missing and not unexpected, (
        f"route inventory drifted.\nmissing: {missing}\nunexpected: {unexpected}"
    )
