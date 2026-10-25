"""Pure adapters from formula ROI results to per-block replacement payloads.

Split from the former formula_service.py monolith (S1 batch 7); zero heavy
imports — dict shaping only. P-040 ③ replaced the append-at-tail adapter with
`build_formula_replacements`: recognition results map back onto their source
layout blocks (keyed by source_id) so the envelope step swaps skip_formula
placeholders in place — keeping block_id / bbox / official reading_order —
instead of filtering placeholders and appending formula blocks at the end of
the page. `build_formula_replacements` is re-exported by the formula_service
facade (orchestration/steps/envelope.py lazy-imports it from there).
"""

from __future__ import annotations

from typing import Any, Dict, List


def build_formula_replacements(
    unwrapped_results: List[Dict[str, Any]],
    source_boxes: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Map ROI recognition results onto their source layout blocks.

    Keyed by source_id (the layout element id ``_collect_layout_blocks`` puts on
    each box and the engine stamps onto every formula_res_list item). An empty
    rec_formula yields ``latex: None`` so the envelope side degrades the block
    in place (``formula_unrecognized``) instead of dropping the region — the
    P-040 ③ ruling. First occurrence wins; ``source_boxes`` is accepted for
    call-site clarity and future validation, positions are not trusted (page
    failures must not shift the mapping).
    """
    replacements: Dict[str, Dict[str, Any]] = {}
    for result_item in unwrapped_results or []:
        if not isinstance(result_item, dict):
            continue
        items = result_item.get("formula_res_list", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            source_id = str(item.get("source_id", "") or "")
            if not source_id or source_id in replacements:
                continue
            latex = str(item.get("rec_formula", "") or "").strip()
            replacements[source_id] = {
                "latex": latex if latex else None,
                "formula_region_id": item.get("formula_region_id"),
            }
    return replacements


def formula_replacement_stats(replacements: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """Quality patch from a replacement map: total regions vs recognized ones."""
    recognized = sum(1 for v in replacements.values() if v.get("latex"))
    return {
        "formula_blocks_total": len(replacements),
        "formula_blocks_recognized": recognized,
    }
