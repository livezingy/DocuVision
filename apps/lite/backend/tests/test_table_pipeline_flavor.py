"""Tests for table pipeline flavor mapping and smart fallback params."""

from app.services.table_pipeline import _build_processor_params, _resolve_user_flavor


def test_resolve_user_flavor_bordered_pdfplumber():
    assert _resolve_user_flavor("pdfplumber", "bordered") == "lines"


def test_resolve_user_flavor_unbordered_camelot():
    assert _resolve_user_flavor("camelot", "unbordered") == "stream"


def test_resolve_user_flavor_auto_passthrough():
    assert _resolve_user_flavor("auto", "auto") == "auto"


def test_build_processor_params_includes_smart_fallback_threshold():
    params = _build_processor_params("mixed", "auto", 0.5, "auto", {})
    assert params["smart_camelot_fallback_threshold"] == 0.8
