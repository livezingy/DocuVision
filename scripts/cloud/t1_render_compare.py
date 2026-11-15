#!/usr/bin/env python3
"""T1 渲染对比 · PyMuPDF vs pypdfium2（R-002 pack v1 附件，Ying 2026-11-12 定稿）.

Provenance: agent-bus@7c1ee869 | path: runs/R-002/attachments/t1_render_compare.py
            | fetched: 2026-11-12 | via: bus-fetch -Provenance
            落位依据：runs/R-002/pack.md §6「脚本落 scripts/cloud/t1_render_compare.py，随本 pack 附带交付」。
            本副本内容 = bus 附件原文 + 本 provenance 注记，未改逻辑。

用法（Cloud Studio / 本机，仓根目录执行）:
    pip install pymupdf pypdfium2 pillow
    python scripts/cloud/t1_render_compare.py --pdf-dir test_data/testfiles/pdf --out t1_renders/

输出:
    t1_renders/fitz/*.png        PyMuPDF 基线渲染（scale=2, 等价 Matrix(2,2)）
    t1_renders/pdfium/*.png      pypdfium2 渲染（scale=2）
    t1_renders/t1_report.jsonl   逐页读数（喂 t1-verdict.md 回填）

读数纪律（pack §3 T1）: 像素差本身不是 fail 判据；本脚本读数 = 下游三闸验证的输入。
三闸（金样 45 restamp / 表格对齐 / 公式 ROI）漂移 = 停 + 回报，无自愈分支。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops


def render_fitz(pdf_path: Path, page_idx: int, scale: float = 2.0) -> Image.Image:
    import fitz  # PyMuPDF

    with fitz.open(pdf_path) as doc:
        pix = doc[page_idx].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def render_pdfium(pdf_path: Path, page_idx: int, scale: float = 2.0) -> Image.Image:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        return doc[page_idx].render(scale=scale).to_pil().convert("RGB")
    finally:
        doc.close()


def diff_stats(a: Image.Image, b: Image.Image) -> dict:
    if a.size != b.size:
        return {"size_fitz": list(a.size), "size_pdfium": list(b.size), "size_match": False}
    d = ImageChops.difference(a, b).convert("L")
    hist = d.histogram()
    changed = sum(hist[1:])
    total = a.size[0] * a.size[1]
    return {
        "size_match": True,
        "changed_px_pct": round(changed / total * 100, 2),
        "max_gray_diff": max((i for i, c in enumerate(hist) if c), default=0),
        "bbox": d.getbbox(),
        "identical": changed == 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-dir", required=True)
    ap.add_argument("--out", default="t1_renders")
    ap.add_argument("--scale", type=float, default=2.0)
    args = ap.parse_args()

    out = Path(args.out)
    (out / "fitz").mkdir(parents=True, exist_ok=True)
    (out / "pdfium").mkdir(parents=True, exist_ok=True)

    pdfs = sorted(Path(args.pdf_dir).glob("*.pdf"))
    if not pdfs:
        print(f"no pdf under {args.pdf_dir}", file=sys.stderr)
        return 1

    report_path = out / "t1_report.jsonl"
    n_pages = 0
    with report_path.open("w", encoding="utf-8") as rpt:
        for pdf in pdfs:
            import fitz  # 仅取页数

            with fitz.open(pdf) as doc:
                n = len(doc)
            for i in range(n):
                n_pages += 1
                tag = f"{pdf.stem}_p{i + 1:03d}"
                im_a = render_fitz(pdf, i, args.scale)
                im_b = render_pdfium(pdf, i, args.scale)
                im_a.save(out / "fitz" / f"{tag}.png")
                im_b.save(out / "pdfium" / f"{tag}.png")
                rec = {"pdf": pdf.name, "page": i + 1, "tag": tag, **diff_stats(im_a, im_b)}
                rpt.write(json.dumps(rec, ensure_ascii=False) + "\n")
                print(f"{tag}: {json.dumps({k: v for k, v in rec.items() if k != 'tag'}, ensure_ascii=False)}")

    print(f"\ndone: {n_pages} pages -> {report_path}")
    print("next: 用 t1_renders/pdfium/ 替换渲染源跑下游三闸（见 pack §6 步 2-4），读数回填 t1-verdict.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
