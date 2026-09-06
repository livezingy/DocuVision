"""Symbol survival benchmark: PP-OCR vs Qwen2.5-VL (GLM trial P1-5).

Why
---
The Upwork JD calls out special glyphs (check mark, tensor product, filled
and open dots). PP-OCR's default charset frequently drops or replaces such
symbols; a multimodal model usually reads them but costs more per page.
This benchmark quantifies the trade-off on the operator's own environment
and produces the model-routing evidence for the trial write-up.

Two engines, one synthetic grid image (PIL-rendered, deterministic):
  - Path A: PP-OCR (app.services.ocr_service)            [GPU/cloud]
  - Path B: Qwen2.5-VL via transformers, plain read prompt [GPU/cloud]

Usage (Cloud Studio, backend venv active, from backend/ cwd):
    python ../scripts/trial/symbol_benchmark.py --out ../outputs/symbol_bench
    python ../scripts/trial/symbol_benchmark.py --render-only   # CPU-safe smoke

Acceptance (see docs/demo/TRIAL_REMOTE_60MIN.md):
    outputs symbol_bench/report.json with per-symbol per-engine
    hit/miss + survival rates + per-engine timing.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, List

SYMBOLS = ["✓", "⊗", "●", "○"]

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/seguisym.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

GRID_COLS = 4  # one symbol per cell, cells numbered


def find_font(override: str = "") -> str:
    if override and os.path.isfile(override):
        return override
    for candidate in FONT_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    raise SystemExit(
        "[error] No symbol-capable font found. Pass --font /path/to/font.ttf "
        "(DejaVu Sans on Linux, Segoe UI Symbol on Windows)."
    )


def render_grid(out_path: str, font_path: str, cell_px: int = 160, reps: int = 3) -> List[Dict[str, Any]]:
    """Render a numbered grid: reps x len(SYMBOLS) cells, one symbol each.

    Returns the ground-truth manifest [{cell_id, symbol}] for scoring.
    """
    from PIL import Image, ImageDraw, ImageFont

    n_cells = len(SYMBOLS) * reps
    rows = (n_cells + GRID_COLS - 1) // GRID_COLS
    img = Image.new("RGB", (GRID_COLS * cell_px, rows * cell_px), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_big = ImageFont.truetype(font_path, int(cell_px * 0.45))
    font_small = ImageFont.truetype(font_path, int(cell_px * 0.14))

    manifest: List[Dict[str, Any]] = []
    for i in range(n_cells):
        symbol = SYMBOLS[i % len(SYMBOLS)]
        col, row = i % GRID_COLS, i // GRID_COLS
        x0, y0 = col * cell_px, row * cell_px
        draw.rectangle([x0, y0, x0 + cell_px - 1, y0 + cell_px - 1], outline=(120, 120, 120), width=2)
        cell_id = f"cell{i + 1:02d}"
        w = draw.textbbox((0, 0), symbol, font=font_big)
        draw.text((x0 + (cell_px - (w[2] - w[0])) / 2, y0 + (cell_px - (w[3] - w[1])) / 2 - cell_px * 0.05), symbol, fill=(0, 0, 0), font=font_big)
        draw.text((x0 + 6, y0 + 4), cell_id, fill=(150, 150, 150), font=font_small)
        manifest.append({"cell_id": cell_id, "symbol": symbol})

    img.save(out_path)
    return manifest


def run_pp_ocr(image_path: str) -> Dict[str, Any]:
    """Path A: PP-OCR full-text read. Returns {text, elapsed_ms}."""
    from app.services.ocr_service import ocr_service  # noqa: PLC0415 — cloud import

    t0 = time.perf_counter()
    result = ocr_service.recognize(image_path, language="en")
    elapsed = int((time.perf_counter() - t0) * 1000)
    # contract: {"text": [...], ...} or list of blocks (engine-dependent)
    texts: List[str] = []
    if isinstance(result, dict):
        for item in result.get("text") or result.get("texts") or []:
            texts.append(str(item))
        blocks = result.get("blocks") or []
        for block in blocks:
            if isinstance(block, dict) and block.get("text"):
                texts.append(str(block["text"]))
    elif isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and item.get("text"):
                texts.append(str(item["text"]))
    return {"text": " ".join(texts), "elapsed_ms": elapsed}


def run_qwen_vl(image_path: str, model_id: str) -> Dict[str, Any]:
    """Path B: Qwen2.5-VL plain read. Returns {text, elapsed_ms}."""
    import torch  # noqa: F401 — ensures GPU stack present
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    t0 = time.perf_counter()
    processor = AutoProcessor.from_pretrained(model_id)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id, torch_dtype="auto", device_map="auto"
    )
    from PIL import Image

    image = Image.open(image_path).convert("RGB")
    prompt = (
        "This image shows numbered cells, each containing exactly one symbol. "
        "List each cell id and the symbol inside it as JSON: "
        '{"cell01": "<symbol>", ...}. Symbols may include check marks and dots. '
        "Respond with JSON only."
    )
    inputs = processor(text=prompt, images=image, return_tensors="pt").to(model.device)
    generated = model.generate(**inputs, max_new_tokens=200)
    out = processor.batch_decode(generated, skip_special_tokens=True)[0]
    return {"text": out, "elapsed_ms": int((time.perf_counter() - t0) * 1000)}


def score(manifest: List[Dict[str, Any]], raw: str) -> Dict[str, Any]:
    """Score per-symbol hit/miss from raw engine text."""
    text = raw or ""
    per_symbol: Dict[str, Dict[str, int]] = {s: {"hit": 0, "miss": 0} for s in SYMBOLS}
    for entry in manifest:
        symbol = entry["symbol"]
        # cell-scoped check: symbol found near its cell id, else global presence
        cell = entry["cell_id"]
        window = text[max(0, text.find(cell)) : text.find(cell) + 40] if cell in text else ""
        if symbol in window or (symbol in text and cell not in text):
            per_symbol[symbol]["hit"] += 1
        else:
            per_symbol[symbol]["miss"] += 1
    total_hit = sum(v["hit"] for v in per_symbol.values())
    total = sum(v["hit"] + v["miss"] for v in per_symbol.values())
    return {
        "per_symbol": per_symbol,
        "survival_rate": round(total_hit / total, 4) if total else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Symbol survival benchmark (GLM P1-5)")
    parser.add_argument("--out", default="../outputs/symbol_bench", help="output dir (default ../outputs/symbol_bench)")
    parser.add_argument("--font", default="", help="symbol-capable TTF path")
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-VL-7B-Instruct")
    parser.add_argument("--reps", type=int, default=3, help="repetitions per symbol")
    parser.add_argument("--render-only", action="store_true", help="render grid and exit (CPU-safe)")
    parser.add_argument("--skip-vl", action="store_true", help="run PP-OCR only")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    font_path = find_font(args.font)
    grid_path = os.path.join(args.out, "symbol_grid.png")
    manifest = render_grid(grid_path, font_path, reps=args.reps)
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[render] {grid_path} ({len(manifest)} cells)")

    if args.render_only:
        print("[render-only] done. Inspect the PNG: each cell must show its symbol.")
        return 0

    report: Dict[str, Any] = {"grid": grid_path, "engines": {}}

    print("[run] PP-OCR ...")
    try:
        ocr_raw = run_pp_ocr(grid_path)
        report["engines"]["pp_ocr"] = {**ocr_raw, **score(manifest, ocr_raw["text"])}
    except Exception as exc:  # noqa: BLE001 — report and continue to VL
        report["engines"]["pp_ocr"] = {"error": str(exc)}
        print(f"[warn] PP-OCR failed: {exc}")

    if not args.skip_vl:
        print(f"[run] Qwen2.5-VL ({args.model_id}) ...")
        try:
            vl_raw = run_qwen_vl(grid_path, args.model_id)
            report["engines"]["qwen_vl"] = {**vl_raw, **score(manifest, vl_raw["text"])}
        except Exception as exc:  # noqa: BLE001
            report["engines"]["qwen_vl"] = {"error": str(exc)}
            print(f"[warn] Qwen2.5-VL failed: {exc}")

    out_json = os.path.join(args.out, "report.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[done] {out_json}")
    for name, res in report["engines"].items():
        if "error" in res:
            print(f"  {name}: ERROR {res['error']}")
        else:
            rate = res.get("survival_rate")
            rate_s = "n/a" if rate is None else f"{rate * 100:.1f}%"
            print(f"  {name}: survival={rate_s} elapsed={res.get('elapsed_ms')}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
