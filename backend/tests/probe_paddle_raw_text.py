#!/usr/bin/env python3
"""
Standalone probe for raw text output from PaddleOCR and PPStructureV3.

Environment target:
- Python 3.10
- paddlepaddle-gpu 3.3.0
- paddleocr 3.3.2
- paddlex 3.3.12

This script does NOT import any project code.
It prints raw text as repr(...) so spaces/newlines are visible.
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from typing import Any, Iterable, List


def _flatten_text(value: Any) -> List[str]:
    """Recursively collect text-like fields from nested outputs."""
    texts: List[str] = []

    if value is None:
        return texts

    if isinstance(value, str):
        texts.append(value)
        return texts

    if isinstance(value, dict):
        for key in ("text", "rec_text", "transcription", "label", "content"):
            v = value.get(key)
            if isinstance(v, str):
                texts.append(v)
        for v in value.values():
            texts.extend(_flatten_text(v))
        return texts

    if isinstance(value, (list, tuple)):
        for item in value:
            texts.extend(_flatten_text(item))
        return texts

    for attr in ("text", "rec_text", "ocr_text", "content"):
        try:
            v = getattr(value, attr, None)
        except Exception:
            v = None
        if isinstance(v, str):
            texts.append(v)

    for attr in (
        "preds",
        "boxes",
        "layout_dets",
        "parsing_res_list",
        "table_res_list",
        "ocr_res",
        "rec_res",
    ):
        try:
            v = getattr(value, attr, None)
        except Exception:
            v = None
        if v is not None:
            texts.extend(_flatten_text(v))

    return texts


def _dedupe_keep_order(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if not x:
            continue
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _print_texts(title: str, texts: List[str]) -> None:
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)

    if not texts:
        print("[No text extracted]")
        return

    for i, t in enumerate(texts, 1):
        # repr keeps raw spaces/newlines visible for debugging.
        print(f"[{i:03d}] {repr(t)}")


def _collect_ppstructure_field_values(result: Any) -> dict:
    """Collect only the requested raw fields from PPStructureV3 output."""
    out = {
        "parsing_res_list.text": [],
        "parsing_res_list.content": [],
        "ocr_res": [],
    }

    if not isinstance(result, (list, tuple)):
        return out

    for page_item in result:
        # Extract parsing_res_list from dict-style or object-style item.
        parsing_res_list = None
        if isinstance(page_item, dict):
            parsing_res_list = page_item.get("parsing_res_list")
            if "ocr_res" in page_item:
                out["ocr_res"].append(page_item.get("ocr_res"))
        else:
            parsing_res_list = getattr(page_item, "parsing_res_list", None)
            if hasattr(page_item, "ocr_res"):
                out["ocr_res"].append(getattr(page_item, "ocr_res", None))

        if isinstance(parsing_res_list, (list, tuple)):
            for block in parsing_res_list:
                if isinstance(block, dict):
                    out["parsing_res_list.text"].append(block.get("text"))
                    out["parsing_res_list.content"].append(block.get("content"))
                else:
                    out["parsing_res_list.text"].append(getattr(block, "text", None))
                    out["parsing_res_list.content"].append(getattr(block, "content", None))

    return out


def _print_raw_field_values(title: str, values: List[Any]) -> None:
    print("\n" + "-" * 90)
    print(title)
    print("-" * 90)

    if not values:
        print("[No values]")
        return

    for i, v in enumerate(values, 1):
        print(f"[{i:03d}] type={type(v).__name__} value={repr(v)}")


def _init_paddleocr_with_space_char(lang: str, device: str):
    """
    Initialize PaddleOCR and force use_space_char=True when the current API supports it.

    Returns:
        (ocr_instance, support_use_space_char)
    """
    from paddleocr import PaddleOCR

    init_kwargs = {"lang": lang, "device": device}
    support_use_space_char = False

    try:
        sig = inspect.signature(PaddleOCR.__init__)
        if "use_space_char" in sig.parameters:
            support_use_space_char = True
            default_value = sig.parameters["use_space_char"].default
            print(f"[OCR] use_space_char supported by API, default={default_value!r}")
            init_kwargs["use_space_char"] = True
            print("[OCR] Forcing use_space_char=True")
        else:
            print(
                "[OCR] use_space_char is NOT exposed in current PaddleOCR API; "
                "space handling is controlled by model/pipeline config."
            )
    except Exception as exc:
        print(f"[OCR] Failed to inspect PaddleOCR signature: {exc}")

    ocr = PaddleOCR(**init_kwargs)
    return ocr, support_use_space_char


def run_ocr_predict(image_path: str, lang: str, device: str) -> None:
    print("\n[OCR] Initializing PaddleOCR...")
    ocr, support_use_space_char = _init_paddleocr_with_space_char(lang, device)
    print(f"[OCR] use_space_char configurable: {support_use_space_char}")

    print("[OCR] Running predict(image_path)...")  
    result = ocr.predict(image_path)

    print("[OCR] Raw output type:", type(result))
    if isinstance(result, (list, tuple)):
        print("[OCR] Raw output length:", len(result))

    # Print minimal JSON-safe shape info for quick inspection.
    try:
        if isinstance(result, list) and result:
            first = result[0]
            if hasattr(first, "keys"):
                print("[OCR] First item keys:", list(first.keys()))
            else:
                print("[OCR] First item attrs sample:", [a for a in dir(first) if not a.startswith("_")][:20])
    except Exception as exc:
        print("[OCR] Failed to inspect first item:", exc)

    texts = _dedupe_keep_order(_flatten_text(result))
    _print_texts("[OCR] Raw text collected from predict()", texts)


def run_ppstructure_predict(image_path: str, lang: str, device: str) -> None:
    from paddleocr import PPStructureV3

    print("\n[PPStructureV3] Initializing PPStructureV3...")
    pp = PPStructureV3(lang=lang, device=device)

    print("[PPStructureV3] Running predict(image_path)...")
    result = pp.predict(image_path)

    print("[PPStructureV3] Raw output type:", type(result))
    if isinstance(result, (list, tuple)):
        print("[PPStructureV3] Raw output length:", len(result))

    try:
        if isinstance(result, list) and result:
            first = result[0]
            if hasattr(first, "keys"):
                print("[PPStructureV3] First item keys:", list(first.keys()))
            else:
                print(
                    "[PPStructureV3] First item attrs sample:",
                    [a for a in dir(first) if not a.startswith("_")][:20],
                )
    except Exception as exc:
        print("[PPStructureV3] Failed to inspect first item:", exc)

    texts = _dedupe_keep_order(_flatten_text(result))
    _print_texts("[PPStructureV3] Raw text collected from predict()", texts)

    fields = _collect_ppstructure_field_values(result)
    _print_raw_field_values(
        "[PPStructureV3] Field raw values: parsing_res_list.text",
        fields["parsing_res_list.text"],
    )
    _print_raw_field_values(
        "[PPStructureV3] Field raw values: parsing_res_list.content",
        fields["parsing_res_list.content"],
    )
    _print_raw_field_values(
        "[PPStructureV3] Field raw values: ocr_res",
        fields["ocr_res"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe raw text output from PaddleOCR OCR and PPStructureV3 predict()"
    )
    parser.add_argument("image", help="Path to test image")
    parser.add_argument("--lang", default="en", help="Language code (default: en)")
    parser.add_argument(
        "--device",
        default="gpu",
        choices=["gpu", "cpu"],
        help="Inference device (default: gpu)",
    )
    parser.add_argument(
        "--save-raw-json",
        default="",
        help="Optional output path to save a coarse JSON dump of text extraction result",
    )

    args = parser.parse_args()

    image_path = os.path.abspath(args.image)
    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}", file=sys.stderr)
        return 2

    print("Python:", sys.version.replace("\n", " "))
    try:
        import paddleocr  # type: ignore

        print("paddleocr version:", getattr(paddleocr, "__version__", "unknown"))
    except Exception as exc:
        print("Failed to import paddleocr version:", exc)

    collected = {}

    try:
        run_ocr_predict(image_path, args.lang, args.device)
        collected["ocr"] = "ok"
    except Exception as exc:
        collected["ocr"] = f"error: {exc}"
        print("\n[OCR] ERROR:", repr(exc), file=sys.stderr)

    try:
        run_ppstructure_predict(image_path, args.lang, args.device)
        collected["ppstructurev3"] = "ok"
    except Exception as exc:
        collected["ppstructurev3"] = f"error: {exc}"
        print("\n[PPStructureV3] ERROR:", repr(exc), file=sys.stderr)

    if args.save_raw_json:
        try:
            with open(args.save_raw_json, "w", encoding="utf-8") as f:
                json.dump(collected, f, ensure_ascii=False, indent=2)
            print(f"\nSaved run status JSON to: {args.save_raw_json}")
        except Exception as exc:
            print(f"\nFailed to save JSON: {exc}", file=sys.stderr)

    if collected.get("ocr", "").startswith("error") and collected.get("ppstructurev3", "").startswith("error"):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
