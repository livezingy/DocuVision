"""Exit-level PII masking for tax identifiers (P-030a).

Field-level masking of the pipeline result tree: string values matching any
of the three tax-id variants (M3) are rewritten in place to ``[TAX-ID-MASKED]``
so nothing unmasked reaches persistence (``pii_mask_step`` runs before
``finalize_step``, whose ``persist_task_safe`` is the storage point).

Enabled per request via ``enable_pii_mask`` (default off = zero behavior).

Scope ruling (P-030 §4.1, frozen spec): the mask applies to exit field values
only. The ``evidence`` subtree (verbatim quotes, gate verdict already written
by the earlier step) and the ``document_info`` subtree are never touched.
``kie_fields`` is shared by reference with the envelope ``view.fields``
(orchestrator builds ``view["fields"] = ctx["result"]["kie_fields"]``), so
in-place dict mutation propagates to the merged exit view. Envelope raw/fused
text layers are text-level and out of scope for this field-level ruling.
"""

from __future__ import annotations

import re
from typing import Any

MASK_TOKEN = "[TAX-ID-MASKED]"

# Three variants (M3): 3-2-4 SSN-style, 2-7 EIN-style, bare 9 digits.
# \b word boundaries mean the digits must stand as a standalone word: longer
# digit runs (10/11 digits) and letter-adjacent runs (e.g. "A123456789") do
# not match, while hyphen/space/colon-delimited 9-digit values do.
_TAX_ID_PATTERNS = (
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b\d{2}-\d{7}\b"),
    re.compile(r"\b\d{9}\b"),
)

# P-030 §4.1: these result subtrees are exempt from masking (checked at the
# top level of the result dict only).
_EXCLUDED_KEYS = frozenset({"evidence", "document_info"})


def mask_text(text: str) -> tuple:
    """Return ``(masked_text, replacement_count)`` for one string value."""
    masked = text
    count = 0
    for pattern in _TAX_ID_PATTERNS:
        masked, n = pattern.subn(MASK_TOKEN, masked)
        count += n
    return masked, count


def _mask_container(node: Any) -> int:
    """Mask str values inside a dict/list in place; return replacement count."""
    count = 0
    if isinstance(node, dict):
        for key in list(node.keys()):
            value = node[key]
            if isinstance(value, str):
                masked, n = mask_text(value)
                if n:
                    node[key] = masked
                    count += n
            else:
                count += _mask_container(value)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            if isinstance(item, str):
                masked, n = mask_text(item)
                if n:
                    node[i] = masked
                    count += n
            else:
                count += _mask_container(item)
    return count


def mask_result_exit(result: dict) -> int:
    """Mask ``ctx["result"]`` in place; return the replacement count.

    Top-level ``evidence`` and ``document_info`` keys are skipped entirely
    (P-030 §4.1). All other nested string values are scanned against the
    three tax-id variants.
    """
    count = 0
    for key in list(result.keys()):
        if key in _EXCLUDED_KEYS:
            continue
        value = result[key]
        if isinstance(value, str):
            masked, n = mask_text(value)
            if n:
                result[key] = masked
                count += n
        else:
            count += _mask_container(value)
    return count
