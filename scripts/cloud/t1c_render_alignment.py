#!/usr/bin/env python3
"""R-002 T1c · 渲染参数对齐实验（pack v1.3 §7 附件，Ying 2026-11-13 12:22 批「T1c 出包」）.

Provenance: agent-bus@8b6028f8 | path: runs/R-002/attachments/t1c_render_alignment.py
            | fetched: 2026-11-13 | via: bus-fetch -Provenance
            落位依据：runs/R-002/pack.md v1.3 §7「执行命令清单」步 1。
            本副本内容 = bus 附件原文 + 本 provenance 注记，未改逻辑。

命题：pdfium 渲染参数矩阵对齐 fitz 基线 → 像素差收敛 → IoU 回升？
主假设（P2）：fitz get_pixmap 默认画 annots，pypdfium2 render() 默认 draw_annots=False/may_draw_forms=False
  —— cosent-form-test-document（表单 PDF，T1b 像素差最大 15.64%/IoU 崩 0.2222）与该假设同向。

参数矩阵（预写死，禁现场增组）：
  P1 default            = render(scale)                    （对照 = T1b 现行）
  P2 annots+forms       = render(scale, draw_annots=True, may_draw_forms=True)
  P3 P2+no-smoothing    = render(scale, draw_annots=True, may_draw_forms=True,
                                 no_smoothtext=True, no_smoothimage=True, no_smoothpath=True)

判据 A（预写死，无漂移）：P* = 使全页 changed_px_pct 均值最小的组；P* 相对 P1 均值下降 >=50%
  → 参数对齐有效，P* 定为对齐参数（stdout 打印 P* 与 render kwargs，供 T1b 复测令）。
判据 B：无组达 A → 可调参数假设排除 → 引擎重评（回 Ying / P-046 立项层），停 + 回报，无自愈。

用法（Cloud Studio 仓根）:
    python scripts/cloud/t1c_render_alignment.py --pdf-dir test_data/testfiles/pdf --out t1c_renders/
输出:
    t1c_renders/fitz/*.png            fitz 基线（同 t1_render_compare.render_fitz，一次生成）
    t1c_renders/<Pn>/*.png            各参数组 pdfium 渲染
    t1c_renders/t1c_pixel_report.jsonl  组×页 diff 读数
    stdout: 汇总表 + 判据 A/B 自动判定行
exit code: 0 = 判据 A 命中（出 P*）；3 = 判据 B（对齐无效）；4 = 环境不可执行
读数纪律：像素差为本实验的中间读数，终裁决面仍是 T1b 判据（块数∧type 序列∧IoU）复测。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops

PARAM_GROUPS = {
    "P1_default": {},
    "P2_annots_forms": {"draw_annots": True, "may_draw_forms": True},
    "P3_annots_nosmooth": {"draw_annots": True, "may_draw_forms": True,
                           "no_smoothtext": True, "no_smoothimage": True, "no_smoothpath": True},
}
# 判据 A 阈值（预写死）
A_THRESHOLD_PCT = 50.0


def render_fitz(pdf_path: Path, page_idx: int, scale: float = 2.0) -> Image.Image:
    import fitz  # PyMuPDF

    with fitz.open(pdf_path) as doc:
        pix = doc[page_idx].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def render_pdfium(pdf_path: Path, page_idx: int, scale: float = 2.0, **opts) -> Image.Image:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        return doc[page_idx].render(scale=scale, **opts).to_pil().convert("RGB")
    finally:
        doc.close()


def diff_stats(a: Image.Image, b: Image.Image) -> dict:
    if a.size != b.size:
        return {"size_match": False, "size_fitz": list(a.size), "size_pdfium": list(b.size)}
    d = ImageChops.difference(a, b).convert("L")
    hist = d.histogram()
    changed = sum(hist[1:])
    total = a.size[0] * a.size[1]
    return {
        "size_match": True,
        "changed_px_pct": round(changed / total * 100, 2),
        "max_gray_diff": max((i for i, c in enumerate(hist) if c), default=0),
        "identical": changed == 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-dir", required=True)
    ap.add_argument("--out", default="t1c_renders")
    ap.add_argument("--scale", type=float, default=2.0)
    args = ap.parse_args()

    out = Path(args.out)
    try:
        import pypdfium2  # noqa: F401
        import fitz  # noqa: F401
    except Exception as e:
        print(f"UNRUN: 双引擎导入失败: {e!r}")
        return 4

    pdfs = sorted(Path(args.pdf_dir).glob("*.pdf"))
    if not pdfs:
        print(f"no pdf under {args.pdf_dir}", file=sys.stderr)
        return 4

    pages = []  # [(tag, fitz_img)]
    (out / "fitz").mkdir(parents=True, exist_ok=True)
    for pdf in pdfs:
        import fitz

        with fitz.open(pdf) as doc:
            n = len(doc)
        for i in range(n):
            tag = f"{pdf.stem}_p{i + 1:03d}"
            img = render_fitz(pdf, i, args.scale)
            img.save(out / "fitz" / f"{tag}.png")
            pages.append((tag, img))

    rpt_path = out / "t1c_pixel_report.jsonl"
    means = {}
    with rpt_path.open("w", encoding="utf-8") as rpt:
        for gname, opts in PARAM_GROUPS.items():
            gdir = out / gname
            gdir.mkdir(parents=True, exist_ok=True)
            pcts = []
            for tag, base in pages:
                pdf = next(p for p in pdfs if tag.startswith(p.stem + "_p"))
                idx = int(tag.rsplit("_p", 1)[1]) - 1
                img = render_pdfium(pdf, idx, args.scale, **opts)
                img.save(gdir / f"{tag}.png")
                rec = {"group": gname, "tag": tag, **diff_stats(base, img)}
                rpt.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if rec.get("size_match"):
                    pcts.append(rec["changed_px_pct"])
                print(f"{gname} {tag}: {json.dumps(rec, ensure_ascii=False)}")
            means[gname] = round(sum(pcts) / len(pcts), 2) if pcts else None

    print("\n=== 参数矩阵汇总（changed_px_pct 均值，越小越贴 fitz）===")
    for g, m in means.items():
        print(f"{g}: {m}%")
    p1 = means.get("P1_default")
    hit = None
    if p1 is not None:
        best_g, best_m = min(((g, m) for g, m in means.items() if m is not None), key=lambda x: x[1])
        drop = round((p1 - best_m) / p1 * 100, 1)
        hit = best_g if drop >= A_THRESHOLD_PCT else None
        print(f"\nbest={best_g} ({best_m}%) vs P1 ({p1}%)  降幅={drop}%  阈值={A_THRESHOLD_PCT}%")
        if hit:
            print(f"JUDGEMENT=A_PASS  P*={hit}  对齐参数={json.dumps(PARAM_GROUPS[hit])}")
            print("next: 以 P* 参数重产双集（t1_render_compare.py 改 render kwargs 或用本组 png）→ T1b 复测（t1b_downstream_diff.py）")
            return 0
        print(f"JUDGEMENT=B_NOALIGN  无组达标（最佳降幅 {drop}% < {A_THRESHOLD_PCT}%）→ 可调参数假设排除")
        print("next: 引擎重评回 Ying / P-046 立项层（停 + 回报，无自愈）")
        return 3
    print("JUDGEMENT=UNRUN  P1 均值缺失（渲染异常）")
    return 4


if __name__ == "__main__":
    sys.exit(main())
