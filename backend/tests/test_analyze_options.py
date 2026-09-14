"""Tests for AnalyzeOptions -> pipeline dict conversion (C2)."""

from __future__ import annotations

from app.models.analyze_options import AnalyzeOptions, options_to_pipeline_dict


def test_defaults() -> None:
    ao = AnalyzeOptions()
    d = options_to_pipeline_dict(ao, table_allow_fullpage_fallback_default=False)
    assert d["enable_layout"] is True
    assert d["table_allow_fullpage_fallback"] is False
    assert d["kie_query_fields"] == []
    assert d["kie_pages"] == "1"
    assert d["table_text_backfill"] == "auto"
    assert "table_template" not in d


def test_fallback_default_applied_when_unset() -> None:
    ao = AnalyzeOptions(table_allow_fullpage_fallback=None)
    d = options_to_pipeline_dict(ao, table_allow_fullpage_fallback_default=True)
    assert d["table_allow_fullpage_fallback"] is True


def test_request_fallback_wins_over_default() -> None:
    ao = AnalyzeOptions(table_allow_fullpage_fallback=False)
    d = options_to_pipeline_dict(ao, table_allow_fullpage_fallback_default=True)
    assert d["table_allow_fullpage_fallback"] is False


def test_table_template_lower_stripped() -> None:
    ao = AnalyzeOptions(table_template="  Bank_Statement ")
    d = options_to_pipeline_dict(ao, table_allow_fullpage_fallback_default=False)
    assert d["table_template"] == "bank_statement"


def test_kie_query_fields_empty_string_becomes_list() -> None:
    ao = AnalyzeOptions(kie_query_fields="   ")
    d = options_to_pipeline_dict(ao, table_allow_fullpage_fallback_default=False)
    assert d["kie_query_fields"] == []


def test_backfill_kill_switch_overrides_request() -> None:
    ao = AnalyzeOptions(table_text_backfill="auto")
    d = options_to_pipeline_dict(
        ao,
        table_allow_fullpage_fallback_default=False,
        table_text_backfill_kill_switch="off",
    )
    assert d["table_text_backfill"] == "off"


def test_backfill_request_value_used_when_no_kill_switch() -> None:
    ao = AnalyzeOptions(table_text_backfill="off")
    d = options_to_pipeline_dict(ao, table_allow_fullpage_fallback_default=False)
    assert d["table_text_backfill"] == "off"
