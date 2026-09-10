"""Unified analyze options (v1.8 §5 / C2).

Both analyze routes (``POST /api/v1/analyze`` legacy and
``POST /api/v1/documents:analyze`` v1) share the same 24 Form parameters.
Before v1.8 they each hand-built an options dict; any new parameter had to
be wired twice. This model is the single authority, and
:func:`options_to_pipeline_dict` produces the orchestrator-facing dict.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel


class AnalyzeOptions(BaseModel):
    """The 24 shared analyze Form parameters plus the v1.8 backfill switch.

    Field names are the diff anchor — do not rename without updating both
    routes and the OpenAPI snapshot test.
    """

    enable_layout: bool = True
    enable_table: bool = True
    enable_formula: bool = False
    enable_seal: bool = False
    enable_figure_export: bool = True
    enable_kie: bool = False
    document_type: str = "auto"
    language: str = "en"
    ocr_engine: Optional[str] = None
    layout_engine: Optional[str] = None
    table_engine: Optional[str] = None
    table_allow_fullpage_fallback: Optional[bool] = None
    formula_disable_layout: bool = False
    formula_disable_preprocess: bool = False
    formula_two_stage_threshold_retry: bool = True
    formula_primary_layout_threshold: float = 0.5
    formula_fallback_layout_threshold: float = 0.2
    formula_layout_threshold: Optional[float] = None
    pipeline_formula_batch_size: int = 1
    return_raw: bool = False
    kie_query_fields: Optional[str] = None
    kie_pages: Optional[str] = None
    table_template: Optional[str] = None
    enable_hitl: bool = True
    # v1.8 新增
    table_text_backfill: Literal["off", "auto"] = "auto"


def options_to_pipeline_dict(
    options: AnalyzeOptions,
    *,
    table_allow_fullpage_fallback_default: bool,
    table_text_backfill_kill_switch: str = "auto",
) -> Dict[str, Any]:
    """Convert an :class:`AnalyzeOptions` into the orchestrator options dict.

    ``table_allow_fullpage_fallback_default`` is the service-level default
    used when the request leaves ``table_allow_fullpage_fallback`` unset.

    ``table_text_backfill_kill_switch`` is the env-level kill switch: when
    it is ``"off"`` the request-level value cannot turn backfill back on.
    """
    data: Dict[str, Any] = options.model_dump()

    data["table_allow_fullpage_fallback"] = (
        table_allow_fullpage_fallback_default
        if options.table_allow_fullpage_fallback is None
        else bool(options.table_allow_fullpage_fallback)
    )

    kqf = options.kie_query_fields
    data["kie_query_fields"] = kqf if (kqf and str(kqf).strip()) else []
    data["kie_pages"] = (options.kie_pages or "").strip() or "1"

    if options.table_template and str(options.table_template).strip():
        data["table_template"] = str(options.table_template).strip().lower()
    else:
        data.pop("table_template", None)

    data["table_text_backfill"] = (
        "off" if table_text_backfill_kill_switch == "off" else options.table_text_backfill
    )

    return data
