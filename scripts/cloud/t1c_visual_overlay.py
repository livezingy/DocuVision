#!/usr/bin/env python3
"""R-002 T1c · 可视化抽验（pack v1.3 §7 附件，Ying 2026-11-13 12:22 批「T1c 出包」）.

Provenance: agent-bus@8b6028f8 | path: runs/R-002/attachments/t1c_visual_overlay.py
            | fetched: 2026-11-13 | via: bus-fetch -Provenance
            落位依据：runs/R-002/pack.md v1.3 §7「执行命令清单」步 2。
            local-compat-patch（2026-11-13，申报 agentD）：①导入双根——仓内约定 sys.path 根 = backend/
            （layout_engine_ppstructure.py:19-21 顶层 `from app...`），附件仅插仓根时两条链皆
            `No module named 'app'`（Cloud Studio 实测，与 T1b 缺陷卡 report-20261113-t1b-attachment-defects
            修 1 同源且 v1.2.1 收编件同病）；②加 --fitz-dir/--pdfium-dir——pack §7 前置允许
            「t1c_render_alignment P1 组顶替」但附件写死 t1_renders/，开口不改变默认行为。
            判读对象/输出格式/判读纪律零改动。待 agentD 出 v1.3.1 后回退本补丁。

命题：对 T1b IoU 崩页 + 过闸对照页，出双引擎 PP-Structure 块框叠加图，人工二值判读：
  ① 边界真漂移（红绿框整体平移/形态变化 → 渲染通道差异真实影响版面检测）
  ② 配对面低估（红绿框各自合理但错位配对 → 贪心最近配对低估贡献，判据面待议不改读数）
判读结论只作解释性证据，不改 T1b PASS/DRIFT 判定（判据面不动——Ying 批口径）。

抽验页（预写死 = T1b 崩页 3 + 过闸对照 1，tag 同 t1_render_compare 命名）:
  cosent-form-test-document_p001（IoU 崩，像素差最大 15.64%）
  sample_report_p001（IoU 崩 0.0714）
  pub_bmcpubh_PMC13595506_p8-10_p002（IoU 崩 0.0909）
  cosent-form-test-document_p002（过闸对照 IoU=1.0）

用法（Cloud Studio 仓根，GPU）:
    python scripts/cloud/t1c_visual_overlay.py --pdf-dir test_data/testfiles/pdf --out t1c_overlays/
    # 前置缺 t1_renders/（T1b 产物已清）时，用 t1c_render_alignment P1 组顶替（同参渲染）：
    python scripts/cloud/t1c_visual_overlay.py --pdf-dir test_data/testfiles/pdf --out t1c_overlays/ \
        --fitz-dir t1c_renders/fitz --pdfium-dir t1c_renders/P1_default
输出:
    t1c_overlays/<tag>.png   fitz 底图 + 绿框(fitz 引擎检测) + 红框(pdfium 引擎检测)
    t1c_overlays/t1c_overlay_report.md  判读回填模板（含逐页预填读数）
附件纪律：叠加 PNG 不上协议仓（判读结论文字回填卡；如需上仓按 v1.7 §5.3.2 ≤3 张 ≤300KB 压缩精选）。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

DEFAULT_PAGES = [
    "cosent-form-test-document_p001",
    "sample_report_p001",
    "pub_bmcpubh_PMC13595506_p8-10_p002",
    "cosent-form-test-document_p002",
]
GREEN, RED = (0, 200, 0), (220, 0, 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-dir", required=True)
    ap.add_argument("--out", default="t1c_overlays")
    ap.add_argument("--pages", nargs="*", default=DEFAULT_PAGES)
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--gpu", action="store_true")
    # local-compat-patch ②：渲染源开口（默认行为不变 = t1_renders/ 双集；P1 顶替见 docstring 用法）
    ap.add_argument("--fitz-dir", default=None,
                    help="fitz 渲染集目录（默认 <仓根>/t1_renders/fitz；P1 顶替 = t1c_renders/fitz）")
    ap.add_argument("--pdfium-dir", default=None,
                    help="pdfium 渲染集目录（默认 <仓根>/t1_renders/pdfium；P1 顶替 = t1c_renders/P1_default）")
    args = ap.parse_args()

    # local-compat-patch ①：导入双根——仓内约定 sys.path 根 = backend/（引擎模块顶层 `from app...`），
    # 附件仅插仓根时两条链皆 `No module named 'app'`（Cloud Studio 实测）；判读/输出零改动。
    _repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_repo))
    sys.path.insert(0, str(_repo / "backend"))
    try:
        from app.services.layout_engine_ppstructure import PPStructureEngine
    except ModuleNotFoundError:
        try:
            from backend.app.services.layout_engine_ppstructure import PPStructureEngine
        except Exception as e:
            print(f"UNRUN: import PPStructureEngine 失败: {e!r}")
            return 4
    from t1b_downstream_diff import extract_blocks  # 同目录复用 v1.2.1 归一（判据同源）

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    f_dir = Path(args.fitz_dir) if args.fitz_dir else _repo / "t1_renders/fitz"
    p_dir = Path(args.pdfium_dir) if args.pdfium_dir else _repo / "t1_renders/pdfium"
    engine = PPStructureEngine(use_gpu=args.gpu)
    if not engine.is_ready():
        print("UNRUN: 引擎 is_ready()=False")
        return 4

    import fitz
    from PIL import Image, ImageDraw

    rpt = (out / "t1c_overlay_report.md").open("w", encoding="utf-8")
    rpt.write("# T1c 可视化抽验判读回填（人工判读，逐页二值）\n\n")
    rpt.write("> 底图 = fitz 渲染；绿框 = fitz png 喂 PP-Structure 检测块；红框 = pdfium png 喂同引擎检测块。\n")
    rpt.write("> 判读二值：① 边界真漂移（红绿框整体平移/形态变化）② 配对面低估（红绿框各自合理但错位）。\n\n")

    async def run():
        ok = 0
        for tag in args.pages:
            stem, pi = tag.rsplit("_p", 1)
            pdf = Path(args.pdf_dir) / f"{stem}.pdf"
            if not pdf.exists():
                print(f"SKIP: {pdf} 不存在")
                continue
            idx = int(pi) - 1
            f_png = f_dir / f"{tag}.png"
            p_png = p_dir / f"{tag}.png"
            if not f_png.exists() or not p_png.exists():
                print(f"SKIP: {tag} 双集 png 缺失（fitz-dir={f_dir} pdfium-dir={p_dir}；"
                      f"先跑 t1_render_compare.py，或用 t1c P1 组顶替 --fitz-dir t1c_renders/fitz "
                      f"--pdfium-dir t1c_renders/P1_default）")
                continue
            try:
                res_f = await engine._analyze_image(str(f_png))
                res_p = await engine._analyze_image(str(p_png))
                blocks_f = extract_blocks(res_f)
                blocks_p = extract_blocks(res_p)
            except Exception as e:
                print(f"UNRUN: {tag} 引擎/归一失败: {e!r}")
                continue
            img = Image.open(f_png).convert("RGB")
            dr = ImageDraw.Draw(img)
            for t, b in blocks_f:
                dr.rectangle(b, outline=GREEN, width=3)
            for t, b in blocks_p:
                dr.rectangle(b, outline=RED, width=1)
            img.save(out / f"{tag}.png")
            rpt.write(f"## {tag}  blocks: fitz={len(blocks_f)} pdfium={len(blocks_p)}\n")
            rpt.write(f"- 判读（勾选）：☐ ①边界真漂移  ☐ ②配对面低估  ☐ 其他（文字描述）\n\n")
            ok += 1
            print(f"{tag}: fitz={len(blocks_f)} pdfium={len(blocks_p)} -> {out}/{tag}.png")
        rpt.close()
        print(f"\ndone: {ok}/{len(args.pages)} 页叠加图 -> {out}/；判读结论回填 runs/R-002/t1c-verdict.md §3 → push bus")
        return 0 if ok else 4

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
