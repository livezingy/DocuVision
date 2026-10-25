"""Full OpenAPI snapshot — locks the route contract across the
v1.8.2 main.py split (SPLIT-U1).

Local-face test (since the P-039 follow-up ruling, batch 6.5): the former
``DOCUVISION_CLOUD_TESTS`` gate was policy, not necessity — ``app.main``
imports without the paddle stack since P-039, and router assembly is static.
Regenerate the baseline only for deliberate additive changes::

    cd backend
    DOCUVISION_OPENAPI_BASELINE=write pytest tests/test_openapi_snapshot_full.py -q

After the baseline exists, any route/schema change turns this red unless the
baseline is regenerated.

Baseline: ``backend/tests/snapshots/openapi_baseline.json``. ``info.version`` is
excluded because it is bumped per release and is not part of the routing
contract.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

_WRITE = os.environ.get("DOCUVISION_OPENAPI_BASELINE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "write",
}

BASELINE = Path(__file__).resolve().parent / "snapshots" / "openapi_baseline.json"


def _normalized_schema() -> dict:
    from app.main import app

    schema = json.loads(json.dumps(app.openapi()))
    schema.get("info", {}).pop("version", None)
    return schema


def _route_count(schema: dict) -> int:
    return sum(len(ops) for ops in schema.get("paths", {}).values())


def test_openapi_full_snapshot_zero_diff() -> None:
    schema = _normalized_schema()

    if _WRITE or not BASELINE.exists():
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        pytest.skip(f"baseline written: {BASELINE}")

    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert _route_count(schema) == _route_count(expected), (
        f"route count changed: {_route_count(expected)} -> {_route_count(schema)}"
    )
    assert schema == expected, "OpenAPI schema drifted from baseline (regenerate only for deliberate changes)"


def test_openapi_route_count_matches_inventory() -> None:
    # OpenAPI exposes REST paths only; the single WebSocket route
    # (/api/v1/tasks/{task_id}/ws) is excluded -> 55 route decorators - 1 WS = 54.
    assert _route_count(_normalized_schema()) == 54
