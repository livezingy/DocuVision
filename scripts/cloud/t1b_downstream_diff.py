#!/usr/bin/env python3
"""R-002 T1b/T1d · 渲染双集 GPU 下游 diff（pack v1.2 附件；v1.4 判据面修订，Ying 2026-11-13 14:24 批「A 出稿」
   + 14:26 批示「直接评估同一坐标系下不同工具 bbox 的坐标值，不靠肉眼」+ 14:28 批「定稿」）。

Provenance: agent-bus@014fb37f | path: runs/R-002/attachments/t1b_downstream_diff.py（v1.4 原件）
            | fetched: 2026-11-13 | via: bus-fetch -Provenance
            落位依据：runs/R-002/pack.md v1.4 §8 T1d 复测令。
            落位史：v1.2 附件原件 → local-compat-patch（blob 6906338a，云端跑通用）→ v1.2.1 落位回退
            → v1.3.1 落位 → 本件 v1.4（判据面修订 + v1.3.1 双根真修复收编 = 本仓 patch ① 语义，
            patch 义务解除）。逻辑零改动。

v1.4（2026-11-13 agentD，判据面修订——T1c verdict B_NOALIGN 定案引擎内禀差后的裁决路径 A）：
  bbox 判据重写：同 type 贪心最近配对 IoU>=0.9 占比 >=95% → 检出面一致（块数 ∧ type 序列，零容忍不变）
    → 序号一一配对 → 同一坐标系 bbox 坐标数值差直判（归一化页尺寸，零肉眼零配对噪声）：
    |Δcx|<=1.0% 页宽 ∧ |Δcy|<=2.5% 页高 ∧ |Δw|<=5% ∧ |Δh|<=5%（全量 100% 配对块，无比例豁免）。
  页尺寸来源 = fitz 渲染 PNG 尺寸（PIL 实读）。逐块明细 coord_blocks 全量留存 report jsonl（块级审计可回溯）。
  分支预裁决：PASS=全页过 → 放行 AgentE T2-T5；检出面漂移 = 真漂照旧停；坐标差超容差 = DRIFT + 回报
    （位移超 1 字符高实证上限，判据面重开）；UNRUN = 报错原文停。无自愈。
v1.3.1（处置 T1c verdict §0 连带申报，v1.2.1 修 1 走样真修复）：双根 sys.path（仓根 + backend/），模拟自测绿。
v1.2.1（2026-11-13 agentD，处置 local-review 缺陷卡 report-20261113-t1b-attachment-defects）：
  修 2 _norm_box 支持 dict 形态：{x,y,width,height} / {x0,y0,x1,y1}（PP-Structure _analyze_image 实测块 bbox 形态，
     t1_t1b.log 逐块实证）。

前置：先跑 t1_render_compare.py 产出双渲染集（t1_renders/fitz/ 与 t1_renders/pdfium/；T1c P1 组渲染亦同参可用）。
用法（Cloud Studio 仓根，GPU 栈就位后）：
    python scripts/cloud/t1b_downstream_diff.py --fitz-dir t1_renders/fitz \
        --pdfium-dir t1_renders/pdfium --out t1b_report_v14.jsonl --gpu

判据（预写死，无漂移，page 级，v1.4）：
    ① block 数一致（零容忍）
    ② type 序列一致（按引擎返回序，零容忍）
    ③ 检出面一致前提下：序号一一配对，逐块 bbox 坐标差在容差内（|Δcx|<=1.0% 页宽 ∧ |Δcy|<=2.5% 页高
       ∧ |Δw|<=5% ∧ |Δh|<=5%），全量 100% 配对块满足
    页级一致 = ①②③ 全满足；页级漂移 = 任一不满足。
    VERDICT: PASS = 全部页一致（过闸，放行 AgentE T2-T5）
             DRIFT = 任一页漂移（停 + 回报，无自愈分支）
             UNRUN = 引擎不 ready / 结果结构无法归一（附报错原文与结构 dump 前 200 字）
exit code: 0 = PASS; 3 = DRIFT; 4 = UNRUN
读数纪律（pack §3 T1b）: 像素差本身不是 fail 判据；本脚本读数 = T1b 前置闸的唯一裁决面。
"""

import argparse
import asyncio
import json
import math
import sys
from pathlib import Path

EXIT_PASS, EXIT_DRIFT, EXIT_UNRUN = 0, 3, 4

# ---- 结果结构防御性归一（引擎 Dict 键名以实测为准，候选序探测；全失败 = UNRUN） ----
BLOCK_KEYS = ("blocks", "regions", "layout", "results", "elements")
TYPE_KEYS = ("type", "label", "category", "block_type", "class")
BOX_KEYS = ("bbox", "box", "bounding_box", "region", "poly")


def _first(d, keys):
    for k in keys:
        if k in d:
            return d[k]
    return None


def _norm_box(v):
    """把 4 数 / 4 点 / 嵌套列表 / dict 归一为 (x0, y0, x1, y1)；失败返回 None。"""
    if v is None:
        return None
    # dict 形态（v1.2.1 修 2）：{x,y,width,height} / {x0,y0,x1,y1}
    if isinstance(v, dict):
        if all(k in v for k in ("x", "y", "width", "height")):
            try:
                x, y = float(v["x"]), float(v["y"])
                w, h = float(v["width"]), float(v["height"])
                return (min(x, x + w), min(y, y + h), max(x, x + w), max(y, y + h))
            except (TypeError, ValueError):
                return None
        if all(k in v for k in ("x0", "y0", "x1", "y1")):
            try:
                x0, y0, x1, y1 = (float(v[k]) for k in ("x0", "y0", "x1", "y1"))
                return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            except (TypeError, ValueError):
                return None
        return None
    try:
        flat = []
        def _walk(x):
            if isinstance(x, (list, tuple)):
                for e in x:
                    _walk(e)
            elif isinstance(x, (int, float)):
                flat.append(float(x))
        _walk(v)
        if len(flat) == 4:
            x0, y0, x1, y1 = flat
            if x0 > x1:
                x0, x1 = x1, x0
            if y0 > y1:
                y0, y1 = y1, y0
            return (x0, y0, x1, y1)
        if len(flat) == 8:  # 4 点多边形 → 外接矩形
            xs, ys = flat[0::2], flat[1::2]
            return (min(xs), min(ys), max(xs), max(ys))
    except Exception:
        pass
    return None


def extract_blocks(result):
    """从引擎返回 Dict 提取 [(type, (x0,y0,x1,y1)), ...]；结构不识别 → raise。"""
    if not isinstance(result, dict):
        raise ValueError(f"result 非 dict: {type(result)}")
    raw = _first(result, BLOCK_KEYS)
    if raw is None:
        # 兼容单页包裹：{"pages": [...]} 或直接 list
        pages = _first(result, ("pages", "page_results"))
        if pages and isinstance(pages, list) and pages and isinstance(pages[0], dict):
            raw = _first(pages[0], BLOCK_KEYS)
    if not isinstance(raw, list):
        raise ValueError(f"block 列表未命中候选键，结构 dump: {json.dumps(result, ensure_ascii=False, default=str)[:200]}")
    out = []
    for b in raw:
        if not isinstance(b, dict):
            continue
        t = _first(b, TYPE_KEYS) or "unknown"
        box = _norm_box(_first(b, BOX_KEYS))
        if box is None:
            raise ValueError(f"块 bbox 无法归一: {json.dumps(b, ensure_ascii=False, default=str)[:120]}")
        out.append((str(t), box))
    return out


def coord_diff(blocks_a, blocks_b, page_w: float, page_h: float):
    """v1.4 判据（Ying 14:26 批示定稿）：检出面一致 → 序号一一配对 → 同一坐标系下
    直接评估 bbox 坐标数值差（归一化到页尺寸，scale 无关），零肉眼、零贪心配对。

    容差（预写死，pack v1.4 §3 推导链）：dy ≤2.5% 页高（1 字符高 1.9% + 余量）、
    dx ≤1.0% 页宽（判读未报告横向漂移，从严）、dw/dh ≤5%（边界裁剪微变）。
    返回 (all_pass, 逐块明细 list)。"""
    tol = {"dx": 1.0, "dy": 2.5, "dw": 5.0, "dh": 5.0}
    details = []
    for i, ((ta, ba), (_, bb)) in enumerate(zip(blocks_a, blocks_b)):
        cx_a, cy_a = (ba[0] + ba[2]) / 2, (ba[1] + ba[3]) / 2
        cx_b, cy_b = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        dcx = abs(cx_a - cx_b) / page_w * 100
        dcy = abs(cy_a - cy_b) / page_h * 100
        dw = abs((ba[2] - ba[0]) - (bb[2] - bb[0])) / (ba[2] - ba[0]) * 100 if ba[2] > ba[0] else 0.0
        dh = abs((ba[3] - ba[1]) - (bb[3] - bb[1])) / (ba[3] - ba[1]) * 100 if ba[3] > ba[1] else 0.0
        ok = dcx <= tol["dx"] and dcy <= tol["dy"] and dw <= tol["dw"] and dh <= tol["dh"]
        details.append({"i": i, "type": ta, "dcx": round(dcx, 3), "dcy": round(dcy, 3),
                        "dw": round(dw, 3), "dh": round(dh, 3), "pass": ok})
    all_pass = all(d["pass"] for d in details)
    return all_pass, details


def diff_page(res_a, res_b, page_w: float, page_h: float):
    ba, bb = extract_blocks(res_a), extract_blocks(res_b)
    c1 = len(ba) == len(bb)
    c2 = [t for t, _ in ba] == [t for t, _ in bb]
    details, worst = [], None
    if c1 and c2 and ba:
        all_pass, details = coord_diff(ba, bb, page_w, page_h)
        worst = max(details, key=lambda d: max(d["dcx"], d["dcy"]))
        c3 = all_pass
    else:
        c3 = not ba and not bb
    ok = c1 and c2 and c3
    return {
        "n_a": len(ba), "n_b": len(bb),
        "count_equal": c1, "type_seq_equal": c2,
        "coord_pass": c3 if (c1 and c2) else None,
        "worst_block": worst,
        "coord_blocks": details,
        "page_ok": ok,
    }


async def run(args):
    _root = Path(__file__).resolve().parents[2]
    # v1.3.1 修 1（真修复，处置 T1c verdict §0 连带申报）：双根 sys.path——
    #   仓内约定 sys.path 含 backend/（顶层 `from app.services...` :19-21），仓根本身亦入栈。
    #   v1.2.1 修 1 走样：仅插仓根 → 首链 `app.*` 必炸且回退链顶层 import 同炸（form No module named 'app'）。
    for p in (str(_root), str(_root / "backend")):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        from app.services.layout_engine_ppstructure import PPStructureEngine
    except Exception as e:
        print(f"UNRUN: import PPStructureEngine 失败: {e!r}")
        return EXIT_UNRUN
    try:
        engine = PPStructureEngine(use_gpu=args.gpu)
    except Exception as e:
        print(f"UNRUN: 引擎构造失败: {e!r}")
        return EXIT_UNRUN
    if not engine.is_ready():
        print("UNRUN: 引擎 is_ready()=False（GPU 栈未就位）")
        return EXIT_UNRUN

    fitz_dir, pdfium_dir = Path(args.fitz_dir), Path(args.pdfium_dir)
    tags = sorted(p.stem for p in fitz_dir.glob("*.png"))
    if not tags:
        print(f"UNRUN: {fitz_dir} 无 PNG（先跑 t1_render_compare.py）")
        return EXIT_UNRUN
    missing = [t for t in tags if not (pdfium_dir / f"{t}.png").exists()]
    if missing:
        print(f"UNRUN: pdfium 侧缺页 {missing[:3]}")
        return EXIT_UNRUN
    if args.limit:
        tags = tags[: args.limit]

    out_path = Path(args.out)
    n_ok = 0
    with out_path.open("w", encoding="utf-8") as rpt:
        for t in tags:
            try:
                from PIL import Image as _PIL
                with _PIL.open(fitz_dir / f"{t}.png") as _im:
                    page_w, page_h = _im.size
                ra = await engine._analyze_image(str(fitz_dir / f"{t}.png"))
                rb = await engine._analyze_image(str(pdfium_dir / f"{t}.png"))
                rec = {"tag": t, **diff_page(ra, rb, page_w, page_h)}
            except (ValueError, KeyError, TypeError) as e:
                rec = {"tag": t, "page_ok": False, "unrun": True, "err": repr(e)[:300]}
            rpt.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_ok += bool(rec.get("page_ok"))
            print(f"{t}: {'OK' if rec.get('page_ok') else json.dumps(rec, ensure_ascii=False)}")

    verdict = "PASS" if n_ok == len(tags) else "DRIFT"
    print(f"\nVERDICT={verdict} pages_ok={n_ok}/{len(tags)} report={out_path}")
    print("读数回填 runs/R-002/t1b-verdict.md（t1b-verdict-template.md 模板随附件）→ push bus → agentD 审读 → 过闸令")
    return EXIT_PASS if verdict == "PASS" else (EXIT_UNRUN if all("unrun" in json.loads(l) for l in out_path.read_text().splitlines()) else EXIT_DRIFT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fitz-dir", required=True)
    ap.add_argument("--pdfium-dir", required=True)
    ap.add_argument("--out", default="t1b_report.jsonl")
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    sys.exit(asyncio.run(run(ap.parse_args())))
