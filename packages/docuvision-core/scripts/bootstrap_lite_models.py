#!/usr/bin/env python3
"""Bootstrap or verify Lite model weights under docuvision-core/models/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from docuvision_core.utils.easyocr_config import get_easyocr_config
from docuvision_core.utils.model_paths import (
    easyocr_model_dir,
    get_models_root,
    local_model_ready,
    table_transformer_detection_dir,
    table_transformer_structure_dir,
)


def _status() -> int:
    root = get_models_root()
    checks = {
        "models_root": root,
        "table_transformer_detection": local_model_ready(table_transformer_detection_dir()),
        "table_transformer_structure": local_model_ready(table_transformer_structure_dir()),
        "easyocr_craft": (easyocr_model_dir() / "craft_mlt_25k.pth").is_file(),
        "easyocr_english": (easyocr_model_dir() / "english_g2.pth").is_file(),
    }
    for key, value in checks.items():
        print(f"  {key}: {value}")
    missing = [k for k, v in checks.items() if k != "models_root" and not v]
    return 0 if not missing else 1


def _download_easyocr() -> None:
    config = get_easyocr_config()
    ok = config.download_models(["en"])
    if not ok:
        raise SystemExit("EasyOCR model download failed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Lite model weights")
    parser.add_argument(
        "--easyocr-only",
        action="store_true",
        help="Download EasyOCR weights only (HF models handled by shell script)",
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Print model presence and exit",
    )
    args = parser.parse_args()

    if args.status_only:
        return _status()

    if args.easyocr_only:
        _download_easyocr()
        return _status()

    print("Use bootstrap_lite_models.sh for full bootstrap, or pass --easyocr-only / --status-only")
    return _status()


if __name__ == "__main__":
    raise SystemExit(main())
