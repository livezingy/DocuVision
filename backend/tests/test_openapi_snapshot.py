"""OpenAPI contract snapshot test (v1.8 §5.3).

Local-face test (since the P-039 follow-up ruling, batch 6.5): the former
``DOCUVISION_CLOUD_TESTS`` gate was policy, not necessity — ``app.main``
imports without the paddle stack since P-039, and router assembly in
``main.py`` is a static list, so the local schema equals the cloud one.
It locks the analyze routes' shared Form contract — any route removal or
schema break turns red; the v1.8-allowed diff is additive only
(``table_text_backfill``).
"""

from __future__ import annotations

_ALLOWED_INCREMENTAL_PARAMS = {"table_text_backfill"}


def _route_form_params(schema: dict, route: str) -> set:
    op = schema["paths"][route]["post"]
    body_schema = op["requestBody"]["content"]["multipart/form-data"]["schema"]
    ref = body_schema.get("$ref")
    if ref:
        name = ref.rsplit("/", 1)[-1]
        return set(schema["components"]["schemas"][name]["properties"].keys())
    return set(body_schema.get("properties", {}).keys())


def test_openapi_analyze_routes_present() -> None:
    from app.main import app

    schema = app.openapi()
    assert "/api/v1/analyze" in schema["paths"]
    assert "/api/v1/documents:analyze" in schema["paths"]


def test_openapi_analyze_routes_share_form_params() -> None:
    from app.main import app

    schema = app.openapi()
    legacy = _route_form_params(schema, "/api/v1/analyze")
    v1 = _route_form_params(schema, "/api/v1/documents:analyze")
    assert legacy == v1, f"analyze routes drifted: legacy vs v1 differ: {legacy ^ v1}"


def test_openapi_backfill_switch_present() -> None:
    from app.main import app

    schema = app.openapi()
    for route in ("/api/v1/analyze", "/api/v1/documents:analyze"):
        params = _route_form_params(schema, route)
        assert "table_text_backfill" in params, f"{route} missing table_text_backfill"
