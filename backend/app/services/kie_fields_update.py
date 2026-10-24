"""Apply human-reviewed KIE field updates to in-memory task results."""

from __future__ import annotations

from typing import Any, Callable, Dict

from app.services.kie.field_validation import validate_kie_fields


def apply_kie_fields_to_task(
    task: Dict[str, Any],
    fields: Dict[str, Any],
    *,
    policy_resolver: Callable[[Dict[str, Any]], Any],
) -> Dict[str, Any]:
    """``policy_resolver`` (``hitl_policy.resolve_hitl_policy``) is INJECTED by
    the caller (runtime hub, runs/split batch 2) — importing it here would be a
    kie->hitl reverse edge; the runtime hub may import any service."""
    result = task.get("result")
    if not isinstance(result, dict):
        raise ValueError("Task has no result")

    result["kie_fields"] = fields
    view = result.setdefault("view", {})
    if isinstance(view, dict):
        view["fields"] = fields

    options = task.get("options") or {}
    policy = policy_resolver(options)
    validation = validate_kie_fields(fields, policy.validation_rules)
    validation["manual_reviewed"] = True
    result["kie_validation"] = validation

    envelope = task.get("envelope")
    if isinstance(envelope, dict):
        env_view = envelope.setdefault("view", {})
        if isinstance(env_view, dict):
            env_view["fields"] = fields

    return validation
