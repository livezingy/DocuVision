#!/usr/bin/env python3
"""Validate layout of synthetic id_card KIE samples (no OCR, bbox math only)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from generate_kie_id_card_samples import (  # noqa: E402
    SAMPLES,
    load_fonts,
    plan_card_layout,
    validate_layout,
)

_KIE_DIR = _SCRIPT_DIR.parent / "testfiles" / "images" / "kie"


def main() -> int:
    fonts = load_fonts()
    all_errors: list[str] = []

    for spec in SAMPLES:
        blocks, value_x = plan_card_layout(spec, fonts)
        errs = validate_layout(blocks, sample_name=spec["file"])
        if errs:
            all_errors.extend(errs)
            continue
        path = _KIE_DIR / spec["file"]
        if not path.is_file():
            all_errors.append(f"{spec['file']}: missing on disk ({path})")
            continue
        print(f"OK {spec['file']} (value_x={value_x}, blocks={len(blocks)})")

    if all_errors:
        print("Layout validation FAILED:", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"All {len(SAMPLES)} id_card layout plans passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
