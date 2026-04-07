#!/usr/bin/env python3
"""
Probe: Compare PP-StructureV3 block text vs PaddleOCR on original-image crops.

Pipeline:
  1. PP-StructureV3 (use_doc_unwarping=False) → block boundaries (preprocessed space)
                                               + doc_preprocessor_res (angle, input_img)
  2. For each text-type block:
       - Apply inverse rotation matrix → original-image coordinates
       - Crop from doc_preprocessor_res["input_img"]  (= original BGR image)
  3. PaddleOCR(use_angle_cls=False, use_doc_preprocessor=False,
               use_doc_orientation_classify=False).predict(crop)
  4. Print side-by-side comparison: PPStructureV3.content vs OCR text on original crop

Notes:
  - use_doc_unwarping=False because doc-unwarping is NOT invertible.
    If a document requires unwarping the crop still comes from the preprocessed image.
  - angle=-1 or 0 from doc_preprocessor_res means no rotation was applied.
  - This script does NOT import any project code.

Usage:
  python probe_block_ocr_comparison.py /path/to/image.jpg [--lang en] [--device gpu] [--save-crops /tmp/crops]
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


# ── Text-type labels (mirrors envelope_builder._OCR_TEXT_LABELS) ──────────────
_TEXT_LABELS: set = {
    "doc_title", "paragraph_title", "abstract_title", "reference_title",
    "content_title", "text", "abstract", "content", "reference",
    "reference_content", "algorithm", "header", "header_image",
    "footer", "footer_image", "footnote", "figure_title",
    "aside_text", "number", "formula_number",
    "title", "subtitle", "figure_caption", "table_caption",
    "list", "list_item",
}


# ── Coord helpers ──────────────────────────────────────────────────────────────

def _build_rotation_matrix(angle: float, orig_h: int, orig_w: int):
    """
    Reconstruct the same affine matrix used by PaddleX rotate_image().
    Returns (matrix, new_w, new_h).  None when angle <= 0.
    """
    if angle < 1e-7:
        return None, orig_w, orig_h
    center = (orig_w / 2.0, orig_h / 2.0)
    M = cv2.getRotationMatrix2D(center, float(angle), 1.0)
    cos_a = abs(M[0, 0])
    sin_a = abs(M[0, 1])
    new_w = int(orig_h * sin_a + orig_w * cos_a)
    new_h = int(orig_h * cos_a + orig_w * sin_a)
    M[0, 2] += (new_w - orig_w) / 2.0
    M[1, 2] += (new_h - orig_h) / 2.0
    return M, new_w, new_h


def _invert_bbox(bbox_prep: List[float], matrix_inv) -> Tuple[int, int, int, int]:
    """
    Map [x1, y1, x2, y2] from preprocessed space back to original image space
    using the inverse affine matrix.  Returns clamped integers (x1, y1, x2, y2).
    """
    x1p, y1p, x2p, y2p = bbox_prep
    # Transform all four corners
    corners = np.array([
        [x1p, y1p, 1],
        [x2p, y1p, 1],
        [x2p, y2p, 1],
        [x1p, y2p, 1],
    ], dtype=np.float64)
    # matrix_inv is (2, 3); compute dot product
    transformed = corners @ matrix_inv.T  # (4, 2)
    x1 = int(np.floor(transformed[:, 0].min()))
    y1 = int(np.floor(transformed[:, 1].min()))
    x2 = int(np.ceil(transformed[:, 0].max()))
    y2 = int(np.ceil(transformed[:, 1].max()))
    return x1, y1, x2, y2


def _crop(img: np.ndarray, x1: int, y1: int, x2: int, y2: int,
          margin: int = 4) -> np.ndarray:
    H, W = img.shape[:2]
    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(W, x2 + margin)
    y2 = min(H, y2 + margin)
    return img[y1:y2, x1:x2]


# ── OCR result parsing ─────────────────────────────────────────────────────────

def _extract_ocr_lines(ocr_result: Any) -> List[Dict[str, Any]]:
    """
    Extract list of {text, score} dicts from PaddleOCR 3.x predict() output.
    Handles: dict, list[dict], list[Result-object].
    """
    lines: List[Dict[str, Any]] = []

    def _from_dict(d: dict):
        texts = d.get("rec_texts") or d.get("rec_text") or []
        scores = d.get("rec_scores") or []
        for i, t in enumerate(texts):
            t = str(t).strip()
            if not t:
                continue
            s = float(scores[i]) if i < len(scores) else 0.0
            lines.append({"text": t, "score": s})

    if isinstance(ocr_result, dict):
        _from_dict(ocr_result)
    elif isinstance(ocr_result, (list, tuple)):
        for item in ocr_result:
            if isinstance(item, dict):
                _from_dict(item)
            elif hasattr(item, "rec_texts"):
                rec_texts = getattr(item, "rec_texts", []) or []
                rec_scores = getattr(item, "rec_scores", []) or []
                for i, t in enumerate(rec_texts):
                    t = str(t).strip()
                    if not t:
                        continue
                    s = float(rec_scores[i]) if i < len(rec_scores) else 0.0
                    lines.append({"text": t, "score": s})
    return lines


def _reorder_lines(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Re-sort OCR line results by adaptive y-bucket + x-left order.
    Replaces PaddleX SortQuadBoxes 10px hard-coded threshold.
    """
    if len(lines) <= 1:
        return lines

    def _poly_ycenter(ln):
        poly = ln.get("polygon") or []
        if not poly:
            return 0.0
        ys = [float(p[1]) for p in poly if isinstance(p, (list, tuple)) and len(p) >= 2]
        return float(np.mean(ys)) if ys else 0.0

    def _poly_xleft(ln):
        poly = ln.get("polygon") or []
        if not poly:
            return 0.0
        xs = [float(p[0]) for p in poly if isinstance(p, (list, tuple)) and len(p) >= 2]
        return float(min(xs)) if xs else 0.0

    def _poly_height(ln):
        poly = ln.get("polygon") or []
        if not poly:
            return 0.0
        ys = [float(p[1]) for p in poly if isinstance(p, (list, tuple)) and len(p) >= 2]
        return (max(ys) - min(ys)) if ys else 0.0

    heights = [_poly_height(ln) for ln in lines]
    line_h = max(float(np.median([h for h in heights if h > 0]) if any(h > 0 for h in heights) else 8.0), 8.0)
    bucket_sz = line_h * 0.7

    def row_key(ln):
        yc = _poly_ycenter(ln)
        return round(yc / bucket_sz) if bucket_sz > 0 else 0

    return sorted(lines, key=lambda ln: (row_key(ln), _poly_xleft(ln)))


def _join_lines(lines: List[Dict[str, Any]]) -> str:
    return " ".join(ln["text"] for ln in lines if ln.get("text", "").strip())


# ── Main probe ─────────────────────────────────────────────────────────────────

def run_probe(image_path: str, lang: str, device: str, save_crops: str) -> None:

    # ── Step 1: PP-StructureV3 ────────────────────────────────────────────────
    print("\n[STEP 1] Running PP-StructureV3 (use_doc_unwarping=False) ...")
    from paddleocr import PPStructureV3
    pp = PPStructureV3(lang=lang, device=device, use_doc_unwarping=False)
    pp_result = pp.predict(image_path)

    if not pp_result:
        print("[ERROR] PP-StructureV3 returned no result.", file=sys.stderr)
        sys.exit(1)

    page_item = pp_result[0]

    # ── Step 2: Extract preprocessing metadata ───────────────────────────────
    doc_pre = page_item.get("doc_preprocessor_res") if isinstance(page_item, dict) else \
              getattr(page_item, "doc_preprocessor_res", None)

    angle = 0.0
    original_img = None

    if doc_pre is not None:
        raw_angle = doc_pre.get("angle", -1) if isinstance(doc_pre, dict) else \
                    getattr(doc_pre, "angle", -1)
        angle = float(raw_angle) if (raw_angle is not None and raw_angle >= 0) else 0.0

        input_img = doc_pre.get("input_img") if isinstance(doc_pre, dict) else \
                    getattr(doc_pre, "input_img", None)
        if input_img is not None and hasattr(input_img, "shape"):
            original_img = input_img
            if original_img.shape[2] == 3 and original_img.dtype == np.uint8:
                # PaddleX stores as RGB; convert to BGR for cv2 operations
                original_img = cv2.cvtColor(original_img, cv2.COLOR_RGB2BGR)

    if original_img is None:
        print("[INFO] doc_preprocessor_res.input_img not found; loading original image from disk.")
        original_img = cv2.imread(image_path)
        if original_img is None:
            print(f"[ERROR] Cannot read image: {image_path}", file=sys.stderr)
            sys.exit(1)

    h_orig, w_orig = original_img.shape[:2]
    print(f"[INFO] original image: {w_orig}x{h_orig}  angle={angle}")

    # Build inverse rotation matrix
    matrix_fwd, w_prep, h_prep = _build_rotation_matrix(angle, h_orig, w_orig)
    matrix_inv = cv2.invertAffineTransform(matrix_fwd) if matrix_fwd is not None else None
    print(f"[INFO] preprocessed size: {w_prep}x{h_prep}  inverse_rotation_applied={matrix_inv is not None}")

    # ── Step 3: Extract text blocks from parsing_res_list ────────────────────
    parsing_res_list = page_item.get("parsing_res_list", []) if isinstance(page_item, dict) else \
                       getattr(page_item, "parsing_res_list", [])

    print(f"[INFO] Total blocks in parsing_res_list: {len(parsing_res_list)}")

    # ── Step 4: PaddleOCR init ───────────────────────────────────────────────
    # Input is already a clean crop from the original image, so default settings are used.
    print("\n[STEP 4] Initializing PaddleOCR (default settings) ...")
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(lang=lang, device=device)

    # ── Step 5: Per-block crop + comparison ──────────────────────────────────
    print("\n" + "=" * 90)
    print("COMPARISON: PPStructureV3.content  vs  PaddleOCR(original-image crop)")
    print("=" * 90)

    text_block_count = 0

    for idx, block in enumerate(parsing_res_list):
        if isinstance(block, dict):
            block_type = str(block.get("type") or block.get("label") or "unknown").lower()
            structure_content = str(block.get("content") or "")
            bbox_raw = block.get("bbox")
        else:
            block_type = str(getattr(block, "type", None) or getattr(block, "label", "unknown")).lower()
            structure_content = str(getattr(block, "content", "") or "")
            bbox_raw = getattr(block, "bbox", None)

        if block_type not in _TEXT_LABELS:
            continue

        text_block_count += 1
        block_id = f"p1_e{idx}"

        # Parse bbox [x1, y1, x2, y2]
        if isinstance(bbox_raw, (list, tuple)) and len(bbox_raw) >= 4:
            bbox = [float(bbox_raw[0]), float(bbox_raw[1]), float(bbox_raw[2]), float(bbox_raw[3])]
        elif isinstance(bbox_raw, dict):
            x0 = float(bbox_raw.get("x", bbox_raw.get("x0", 0)))
            y0 = float(bbox_raw.get("y", bbox_raw.get("y0", 0)))
            w  = float(bbox_raw.get("width", 0))
            h  = float(bbox_raw.get("height", 0))
            x1b = float(bbox_raw.get("x1", x0 + w))
            y1b = float(bbox_raw.get("y1", y0 + h))
            bbox = [x0, y0, x1b, y1b]
        else:
            print(f"\n[{idx:03d}] id={block_id} type={block_type}  [SKIP: no bbox, raw={repr(bbox_raw)[:60]}]")
            continue

        # Map to original image space
        if matrix_inv is not None:
            x1, y1, x2, y2 = _invert_bbox(bbox, matrix_inv)
        else:
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

        # Clamp to original image bounds
        x1 = max(0, x1);  y1 = max(0, y1)
        x2 = min(w_orig, x2);  y2 = min(h_orig, y2)

        if x2 <= x1 or y2 <= y1:
            print(f"\n[{idx:03d}] id={block_id} type={block_type}  [SKIP: degenerate bbox ({x1},{y1},{x2},{y2})]")
            continue

        crop = _crop(original_img, x1, y1, x2, y2)

        if save_crops:
            os.makedirs(save_crops, exist_ok=True)
            crop_path = os.path.join(save_crops, f"{block_id}_{block_type}.png")
            cv2.imwrite(crop_path, crop)

        # Run PaddleOCR on the original-image crop
        try:
            raw_ocr = ocr.predict(crop)
            lines = _extract_ocr_lines(raw_ocr)
            lines = _reorder_lines(lines)
            ocr_text = _join_lines(lines)
            avg_conf = float(np.mean([ln["score"] for ln in lines])) if lines else 0.0
        except Exception as exc:
            ocr_text = f"[OCR ERROR: {exc}]"
            avg_conf = 0.0

        # Print comparison
        crop_h, crop_w = crop.shape[:2]
        print(f"\n[{idx:03d}] id={block_id} type={block_type}")
        print(f"       bbox_prep=({int(bbox[0])},{int(bbox[1])},{int(bbox[2])},{int(bbox[3])})  "
              f"bbox_orig=({x1},{y1},{x2},{y2})  crop={crop_w}x{crop_h}  ocr_conf={avg_conf:.3f}")
        print(f"  [PPStructV3] {repr(structure_content[:240])}")
        print(f"  [OCR/orig ] {repr(ocr_text[:240])}")

        # Quality indicators
        pp_words  = len(structure_content.split())
        ocr_words = len(ocr_text.split()) if ocr_text and not ocr_text.startswith("[OCR ERROR") else 0
        ratio = ocr_words / pp_words if pp_words > 0 else 0.0
        pp_space  = structure_content.count(" ") / max(len(structure_content), 1)
        ocr_space = ocr_text.count(" ") / max(len(ocr_text), 1) if ocr_text else 0.0
        match = "✓" if abs(ratio - 1.0) < 0.3 else ("✗ SHORT" if ratio < 0.7 else "✗ LONG")
        print(f"  [STATS] pp_words={pp_words} ocr_words={ocr_words} word_ratio={ratio:.2f} {match}  "
              f"pp_space={pp_space:.3f} ocr_space={ocr_space:.3f}")

    print(f"\n{'=' * 90}")
    print(f"[SUMMARY] Text blocks processed: {text_block_count} / {len(parsing_res_list)} total")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare PP-StructureV3 content vs PaddleOCR on original-image crops"
    )
    parser.add_argument("image", help="Path to input image")
    parser.add_argument("--lang", default="en", help="Language code (default: en)")
    parser.add_argument("--device", default="gpu", choices=["gpu", "cpu"],
                        help="Inference device (default: gpu)")
    parser.add_argument("--save-crops", default="",
                        help="Optional directory to save per-block crop images")
    args = parser.parse_args()

    image_path = os.path.abspath(args.image)
    if not os.path.exists(image_path):
        print(f"[ERROR] Image not found: {image_path}", file=sys.stderr)
        return 2

    print("Python:", sys.version.replace("\n", " "))
    try:
        import paddleocr
        print("paddleocr version:", getattr(paddleocr, "__version__", "unknown"))
    except Exception as exc:
        print(f"paddleocr import error: {exc}", file=sys.stderr)
        return 1

    try:
        run_probe(image_path, args.lang, args.device, args.save_crops)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"\n[FATAL] {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
