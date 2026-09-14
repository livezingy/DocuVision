#!/usr/bin/env python3
"""Route architecture lint — stdlib AST only (no imports, no paddle).

Enforces the rules in ``docs/agent-ops/core/routing.md``:
  R1  ``@app.get/post/put/delete/patch/websocket`` decorators live only in
      ``backend/app/routers/*.py`` (never in main.py or services/).
  R2  routers declare ``router = APIRouter()`` with no ``prefix=`` argument
      (paths are written in full; OpenAPI stays byte-identical).
  R3  ``backend/app`` code must not ``from app.main import ...`` /
      ``import app.main`` (no cycle; shared state lives in core/runtime.py).

Until feature/v1.8.2 splits main.py (i.e. ``backend/app/routers/`` does not
exist yet), R1/R2 auto-skip and the check runs R3 only; after the split the
full check is strict. Exit code 0 = pass, 1 = violations.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "backend" / "app"
ROUTERS_DIR = APP_DIR / "routers"

ROUTE_METHODS = {"get", "post", "put", "delete", "patch", "websocket"}


def _py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _route_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Return the method names of ``@app.<method>`` decorators on a function."""
    found: list[str] = []
    for dec in node.decorator_list:
        # @app.get(...) -> ast.Attribute(value=Name('app'), attr='get')
        if isinstance(dec, ast.Attribute) and isinstance(dec.value, ast.Name):
            if dec.value.id == "app" and dec.attr in ROUTE_METHODS:
                found.append(dec.attr)
    return found


def _apirouter_has_prefix(node: ast.Call) -> bool:
    return any(kw.arg == "prefix" for kw in node.keywords)


def _iter_funcs(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _check_file(path: Path, check_r1_r2: bool) -> list[str]:
    """Return a list of violation strings for one file."""
    violations: list[str] = []
    rel = path.relative_to(REPO_ROOT).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)

    in_routers = path.parent == ROUTERS_DIR or ROUTERS_DIR in path.parents

    # R3 — import app.main (always)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app.main" or alias.name.startswith("app.main."):
                    violations.append(f"{rel}:{node.lineno}  R3 import app.main")
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "app.main" or node.module.startswith("app.main.")):
                violations.append(f"{rel}:{node.lineno}  R3 from app.main import ...")

    if not check_r1_r2:
        return violations

    # R1 — route decorators only in routers/
    for node in _iter_funcs(tree):
        methods = _route_decorators(node)
        if methods and not in_routers:
            violations.append(
                f"{rel}:{node.lineno}  R1 route decorator @app.{methods[0]} outside routers/"
            )

    # R2 — APIRouter() must not pass prefix=
    if in_routers:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name == "APIRouter" and _apirouter_has_prefix(node):
                    violations.append(f"{rel}:{node.lineno}  R2 APIRouter(prefix=...) not allowed")

    return violations


def main() -> int:
    check_r1_r2 = ROUTERS_DIR.is_dir()
    if not check_r1_r2:
        print(
            f"[lint_routes] {ROUTERS_DIR.relative_to(REPO_ROOT).as_posix()} missing - "
            "pre-split state; running R3 only (R1/R2 activate after v1.8.2 split)"
        )

    all_violations: list[str] = []
    for path in _py_files(APP_DIR):
        all_violations.extend(_check_file(path, check_r1_r2))

    if all_violations:
        for v in all_violations:
            print(f"[FAIL] {v}")
        print(f"[lint_routes] {len(all_violations)} violation(s)")
        return 1

    print("[lint_routes] OK" + ("" if check_r1_r2 else " (pre-split: R3 only)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
