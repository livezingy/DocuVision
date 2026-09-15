"""Frozen route contract — the local, paddle-free approximation of SPLIT-U1.

FastAPI derives each OpenAPI operation from the endpoint's **function name**
(operationId), **signature** (parameters), **docstring** (description) and
**decorator keywords** (response_model / status_code / ...). This test AST-scans
``app/main.py`` + ``app/routers/*.py`` and compares that contract surface against
``tests/snapshots/route_contract_freeze.json``.

Why it exists: the v1.8.2 C2 move was meant to be a pure relocation, but it
rewrote a route docstring — which silently changed the OpenAPI ``description``.
Only the cloud-only full snapshot could see it (``test_openapi_snapshot_full.py``
needs the paddle stack). This test catches that class of drift locally in under a
second.

Regenerate only for **deliberate** route changes::

    cd backend
    DOCUVISION_ROUTE_FREEZE=write pytest tests/test_route_contract_freeze.py -q

Route **bodies** are intentionally not frozen — they legitimately evolve with
feature work; this gate only protects the contract-visible surface.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = REPO_ROOT / "backend" / "app"
MAIN = APP_DIR / "main.py"
ROUTERS_DIR = APP_DIR / "routers"
FREEZE = Path(__file__).resolve().parent / "snapshots" / "route_contract_freeze.json"

_ROUTE_METHODS = {"get", "post", "put", "delete", "patch", "websocket"}
_WRITE = os.environ.get("DOCUVISION_ROUTE_FREEZE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "write",
}


def _target_files() -> list[Path]:
    files = [MAIN]
    if ROUTERS_DIR.is_dir():
        files.extend(sorted(ROUTERS_DIR.rglob("*.py")))
    return files


def _route_of(dec: ast.AST) -> tuple[str, str, str] | None:
    """Return (METHOD, path, decorator_attr) for an ``@app.<m>`` / ``@router.<m>``."""
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
    return method, first.value, func.attr


def collect_contract() -> dict:
    out: dict[str, dict] = {}
    for path in _target_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                route = _route_of(dec)
                if route is None:
                    continue
                method, route_path, _attr = route
                out[f"{method} {route_path}"] = {
                    "name": node.name,
                    "signature": ast.unparse(node.args),
                    "docstring": ast.get_docstring(node),
                    "decorator_kwargs": sorted(
                        [kw.arg, ast.unparse(kw.value)] for kw in dec.keywords
                    ),
                }
    return dict(sorted(out.items()))


def test_route_contract_matches_frozen_baseline() -> None:
    current = collect_contract()

    if _WRITE or not FREEZE.exists():
        FREEZE.parent.mkdir(parents=True, exist_ok=True)
        FREEZE.write_text(
            json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        import pytest

        pytest.skip(f"freeze baseline written: {FREEZE}")

    expected = json.loads(FREEZE.read_text(encoding="utf-8"))
    changed = sorted(
        k for k in set(current) | set(expected) if current.get(k) != expected.get(k)
    )
    assert not changed, (
        "route contract drifted from the frozen baseline: "
        + ", ".join(changed)
        + "\nA route was added/removed, or its name / signature / docstring / "
        "decorator keywords changed. For deliberate changes regenerate with: "
        "DOCUVISION_ROUTE_FREEZE=write pytest tests/test_route_contract_freeze.py"
    )
