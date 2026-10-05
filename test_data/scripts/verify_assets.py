#!/usr/bin/env python3
"""verify_assets.py — 客户源资产 / 产出件指纹校验（P-027 RF assets 区，多命名空间）。

默认遍历 `test_data/assets/*/manifest.json`（每个客户命名空间一份），逐文件重算
SHA256 与清单比对；`--manifest` 可指定校验单个清单。兼容两种清单 schema：

    * 源资产清单：顶层 ``assets`` 列表，条目键 ``path``；
    * 产出件清单：顶层 ``artifacts`` 列表，条目键 ``file``
      （P-028 pack，如 `test_data/derived/packs/*/manifest.json`）。

兼容两种指纹口径：

    * ``sha256``（字节级，默认）：源资产等「拷贝归位」件，逐位比对；
    * ``fingerprint.kind == "content"``（内容级）：**由脚本重新生成**的派生产物
      （如 fitz ``select`` + ``save`` 切出的单页包）。PyMuPDF 每次 save 都写入随机
      ``/ID[1]``，故此类产物**字节不可复现**（同命令两次运行 sha256 不同），只能
      以内容指纹为准：``text_sha256`` + ``pages`` + ``words`` + ``rotation``。
      内容级校验需 PyMuPDF；不可用时该条记 ``UNVERIFIED`` 并以非零码退出
      （**绝不静默当成通过**）。

空清单（两列表皆缺/为空）判为 ERROR 并以非零退出码结束，避免键名拼写错误被静默
当成「0 行 OK」（P-028 发现：pack manifest 曾因 schema 不识别而假通过）。

用法：
    python test_data/scripts/verify_assets.py
    python test_data/scripts/verify_assets.py --json
    python test_data/scripts/verify_assets.py --manifest path/to/manifest.json

退出码：0 = 全部匹配；1 = 存在缺失/不符/未验/空清单；2 = 无清单可校验。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS_ROOT = REPO_ROOT / "test_data" / "assets"

CHUNK = 1024 * 1024  # 1 MiB


def sha256_of(path: Path) -> str:
    """分块计算文件 SHA256，返回大写十六进制（与 manifest 一致）。"""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def discover_manifests() -> list[Path]:
    """返回 ``assets/*/manifest.json``（按路径排序）；``assets/`` 缺失时返回 []。"""
    if not ASSETS_ROOT.is_dir():
        return []
    return sorted(ASSETS_ROOT.glob("*/manifest.json"))


def _iter_entries(manifest: dict) -> list[tuple[str, dict]]:
    """返回 (相对路径, 条目) 对，兼容两种清单 schema。

    * 源资产清单：顶层 ``assets`` 列表，条目键 ``path``；
    * 产出件清单：顶层 ``artifacts`` 列表，条目键 ``file``。

    非字典条目跳过；两列表皆缺/为空 -> 返回 []（由 ``main`` 判为 ERROR）。
    """
    pairs: list[tuple[str, dict]] = []
    for entry in manifest.get("assets") or []:
        if isinstance(entry, dict):
            pairs.append((entry.get("path", ""), entry))
    for entry in manifest.get("artifacts") or []:
        if isinstance(entry, dict):
            pairs.append((entry.get("file", ""), entry))
    return pairs


def _norm_fingerprint(fp: dict) -> dict:
    """指纹规范化：去掉 ``kind``；``text_sha256`` 统一大写。"""
    out: dict = {}
    for key, value in fp.items():
        if key == "kind":
            continue
        out[key] = value.strip().upper() if isinstance(value, str) else value
    return out


def _pdf_content_fingerprint(path: Path) -> dict | None:
    """PDF 内容级指纹（需 PyMuPDF）；不可用/不可读时返回 ``None``。"""
    try:
        import fitz
    except Exception:
        return None
    try:
        doc = fitz.open(path)
    except Exception:
        return None
    try:
        if doc.page_count < 1:
            return None
        page = doc[0]
        return {
            "text_sha256": hashlib.sha256(
                page.get_text("text").encode("utf-8")).hexdigest(),
            "pages": doc.page_count,
            "words": len(page.get_text("words")),
            "rotation": page.rotation,
        }
    except Exception:
        return None
    finally:
        doc.close()


def _verify_content_entry(fpath: Path, entry: dict) -> tuple[str, str, str]:
    """内容级校验：返回 ``(status, expected, actual)``。"""
    expected = _norm_fingerprint(entry.get("fingerprint") or {})
    actual_raw = _pdf_content_fingerprint(fpath)
    if actual_raw is None:
        return ("unverified",
                json.dumps(expected, ensure_ascii=False, sort_keys=True),
                "PyMuPDF unavailable or file unreadable")
    actual = _norm_fingerprint(actual_raw)
    return ("ok" if actual == expected else "mismatch",
            json.dumps(expected, ensure_ascii=False, sort_keys=True),
            json.dumps(actual, ensure_ascii=False, sort_keys=True))


def verify(manifest_path: Path) -> tuple[list[dict], dict]:
    """校验单个清单；返回 (逐条结果, 汇总)。支持 assets / artifacts 两种 schema。"""
    manifest = load_manifest(manifest_path)
    base = manifest_path.parent
    results: list[dict] = []

    for rel, entry in _iter_entries(manifest):
        fpath = base / rel

        if not fpath.exists():
            fp = entry.get("fingerprint") or {}
            results.append({
                "path": rel, "status": "missing",
                "expected": (entry.get("sha256") or fp.get("text_sha256") or "").strip().upper(),
                "actual": None})
            continue

        if (entry.get("fingerprint") or {}).get("kind") == "content":
            status, expected, actual = _verify_content_entry(fpath, entry)
        else:
            expected = (entry.get("sha256") or "").strip().upper()
            actual_sha = sha256_of(fpath)
            status = "ok" if actual_sha == expected else "mismatch"
            actual = actual_sha
        results.append({"path": rel, "status": status,
                        "expected": expected, "actual": actual})

    summary = {
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "mismatch": sum(1 for r in results if r["status"] == "mismatch"),
        "missing": sum(1 for r in results if r["status"] == "missing"),
        "unverified": sum(1 for r in results if r["status"] == "unverified"),
    }
    return results, summary


def _render_manifest(results: list[dict], summary: dict) -> str:
    lines: list[str] = []
    mark = {"ok": "[OK]     ", "missing": "[MISSING]", "mismatch": "[MISMATCH]",
            "unverified": "[UNVERIFIED]"}
    for r in results:
        lines.append(f"{mark[r['status']]} {r['path']}")
        if r["status"] in ("mismatch", "unverified"):
            lines.append(f"          expected {r['expected']}")
            lines.append(f"          actual   {r['actual']}")
    if (summary["mismatch"] == 0 and summary["missing"] == 0
            and summary["unverified"] == 0):
        lines.append(f"{summary['total']} 行全对 = 0 不符 OK")
    else:
        lines.append(
            f"不符 {summary['mismatch']} / 缺失 {summary['missing']} / 未验 {summary['unverified']}"
            f" / 共 {summary['total']} — 停止，先查归位拷贝是否中断/污染或指纹口径，修复后重算。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="客户源资产 / 产出件指纹校验（多命名空间）")
    parser.add_argument(
        "--manifest", type=Path, default=None,
        help="仅校验指定 manifest.json（默认遍历 test_data/assets/*/manifest.json）")
    parser.add_argument("--json", action="store_true", help="输出 JSON（CI/审计）")
    args = parser.parse_args()

    manifests = [args.manifest] if args.manifest else discover_manifests()
    if not manifests:
        print("no manifest found (test_data/assets/*/manifest.json)", file=sys.stderr)
        return 2

    per: list[dict] = []
    aggregate = {"total": 0, "ok": 0, "mismatch": 0, "missing": 0, "unverified": 0, "empty": 0}
    for m in manifests:
        if not m.exists():
            print(f"manifest not found: {m}", file=sys.stderr)
            return 2
        results, summary = verify(m)
        rel = m.relative_to(REPO_ROOT).as_posix() if m.is_relative_to(REPO_ROOT) else str(m)
        empty = not results
        per.append({"manifest": rel, "summary": summary, "results": results, "empty": empty})
        for key in ("total", "ok", "mismatch", "missing", "unverified"):
            aggregate[key] += summary[key]
        if empty:
            aggregate["empty"] += 1

    if args.json:
        print(json.dumps({"manifests": per, "aggregate": aggregate},
                         ensure_ascii=False, indent=2))
    else:
        blocks: list[str] = []
        for item in per:
            blocks.append(f"== {item['manifest']} ==")
            if item["empty"]:
                blocks.append("[EMPTY]   清单无可校验条目（assets / artifacts 均缺或为空）")
                continue
            blocks.append(_render_manifest(item["results"], item["summary"]))
        blocks.append("")
        if (aggregate["mismatch"] == 0 and aggregate["missing"] == 0
                and aggregate["unverified"] == 0 and aggregate["empty"] == 0):
            blocks.append(f"总计 {aggregate['total']} 行全对 = 0 不符 OK")
        else:
            blocks.append(
                f"总计：不符 {aggregate['mismatch']} / 缺失 {aggregate['missing']} "
                f"/ 未验 {aggregate['unverified']} / 空清单 {aggregate['empty']} "
                f"/ 共 {aggregate['total']} — 停止，先查归位拷贝或清单 schema。")
        print("\n".join(blocks))

    bad = (aggregate["mismatch"] or aggregate["missing"]
           or aggregate["unverified"] or aggregate["empty"])
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
