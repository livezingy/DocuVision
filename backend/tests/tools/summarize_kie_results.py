#!/usr/bin/env python3
"""汇总 Phase C/D/E 导出的 result JSON（quality.kie_*）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.kie.kie_field_metrics import evaluate_kie_contract, evaluate_kie_production_hit


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _pick_quality(body: dict) -> dict:
    q = body.get("quality")
    return q if isinstance(q, dict) else {}


def _pick_fields(body: dict) -> dict:
    kf = body.get("kie_fields")
    if isinstance(kf, dict) and kf:
        return kf
    view = body.get("view") if isinstance(body.get("view"), dict) else {}
    vf = view.get("fields")
    return vf if isinstance(vf, dict) else {}


def summarize_file(path: Path, document_type: str = "invoice") -> None:
    body = _load(path)
    quality = _pick_quality(body)
    fields = _pick_fields(body)
    stage = str(quality.get("kie_stage", "") or "")
    count = int(quality.get("kie_fields_count", 0) or 0)
    doc = str(
        quality.get("document_type")
        or body.get("document_type")
        or document_type
    )
    contract_ok, _ = evaluate_kie_contract(stage, count)
    prod_hit, prod_reason, prod_keys = evaluate_kie_production_hit(doc, fields)
    print(f"\n=== {path.name} ===")
    print(f"  document_type: {doc}")
    print(f"  kie_stage: {stage}")
    print(f"  kie_fields_count: {count}")
    print(f"  kie_production_hit (quality): {quality.get('kie_production_hit')}")
    print(f"  kie_production_reason: {quality.get('kie_production_reason', prod_reason)}")
    print(f"  kie_error_code: {quality.get('kie_error_code', '')}")
    print(f"  kie_error_message: {str(quality.get('kie_error_message', ''))[:200]}")
    print(f"  KIE-ACCEPT-001: {'pass' if contract_ok else 'fail'}")
    print(f"  KIE-ACCEPT-002: {'hit' if prod_hit else 'miss'} ({prod_reason}) keys={prod_keys}")


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        root = _BACKEND.parent / "test_data" / "TestResult" / "PhaseCDE"
        print(f"Usage: python {Path(__file__).name} <dir-or-json> [...]")
        print(f"  default dir: {root}")
        if not root.is_dir():
            sys.exit(1)
        paths = sorted(root.glob("*.json"))
    else:
        paths = []
        for arg in argv[1:]:
            p = Path(arg)
            if p.is_dir():
                paths.extend(sorted(p.glob("*.json")))
            elif p.is_file():
                paths.append(p)

    if not paths:
        print("No JSON files found.")
        sys.exit(1)

    for p in paths:
        summarize_file(p)


if __name__ == "__main__":
    main(sys.argv)
