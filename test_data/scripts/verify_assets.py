#!/usr/bin/env python3
"""verify_assets.py — 客户源资产指纹校验（P-027 RF assets 区，多命名空间）。

默认遍历 `test_data/assets/*/manifest.json`（每个客户命名空间一份），逐文件重算
SHA256 与清单比对；`--manifest` 可指定校验单个清单。输出「0 不符方为有效」的判定，
并以非零退出码供 CI/审计调用。

用法：
    python test_data/scripts/verify_assets.py
    python test_data/scripts/verify_assets.py --json
    python test_data/scripts/verify_assets.py --manifest path/to/manifest.json

退出码：0 = 全部匹配；1 = 存在缺失/不符；2 = 无清单可校验。
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


def verify(manifest_path: Path) -> tuple[list[dict], dict]:
    """校验单个清单；返回 (逐条结果, 汇总)。"""
    manifest = load_manifest(manifest_path)
    base = manifest_path.parent
    results: list[dict] = []

    for entry in manifest.get("assets", []):
        rel = entry.get("path", "")
        expected = (entry.get("sha256") or "").strip().upper()
        fpath = base / rel

        if not fpath.exists():
            results.append({"path": rel, "status": "missing",
                            "expected": expected, "actual": None})
            continue

        actual = sha256_of(fpath)
        results.append({"path": rel,
                        "status": "ok" if actual == expected else "mismatch",
                        "expected": expected, "actual": actual})

    summary = {
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "mismatch": sum(1 for r in results if r["status"] == "mismatch"),
        "missing": sum(1 for r in results if r["status"] == "missing"),
    }
    return results, summary


def _render_manifest(results: list[dict], summary: dict) -> str:
    lines: list[str] = []
    mark = {"ok": "[OK]     ", "missing": "[MISSING]", "mismatch": "[MISMATCH]"}
    for r in results:
        lines.append(f"{mark[r['status']]} {r['path']}")
        if r["status"] == "mismatch":
            lines.append(f"          expected {r['expected']}")
            lines.append(f"          actual   {r['actual']}")
    if summary["mismatch"] == 0 and summary["missing"] == 0:
        lines.append(f"{summary['total']} 行全对 = 0 不符 OK")
    else:
        lines.append(
            f"不符 {summary['mismatch']} / 缺失 {summary['missing']} / 共 {summary['total']} "
            f"— 停止，先查归位拷贝是否中断/污染，修复后重算。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="客户源资产指纹校验（多命名空间）")
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
    aggregate = {"total": 0, "ok": 0, "mismatch": 0, "missing": 0}
    for m in manifests:
        if not m.exists():
            print(f"manifest not found: {m}", file=sys.stderr)
            return 2
        results, summary = verify(m)
        rel = m.relative_to(REPO_ROOT).as_posix() if m.is_relative_to(REPO_ROOT) else str(m)
        per.append({"manifest": rel, "summary": summary, "results": results})
        for key in aggregate:
            aggregate[key] += summary[key]

    if args.json:
        print(json.dumps({"manifests": per, "aggregate": aggregate},
                         ensure_ascii=False, indent=2))
    else:
        blocks: list[str] = []
        for item in per:
            blocks.append(f"== {item['manifest']} ==")
            blocks.append(_render_manifest(item["results"], item["summary"]))
        blocks.append("")
        if aggregate["mismatch"] == 0 and aggregate["missing"] == 0:
            blocks.append(f"总计 {aggregate['total']} 行全对 = 0 不符 OK")
        else:
            blocks.append(f"总计：不符 {aggregate['mismatch']} / 缺失 {aggregate['missing']} "
                          f"/ 共 {aggregate['total']} — 停止，先查归位拷贝。")
        print("\n".join(blocks))

    return 0 if (aggregate["mismatch"] == 0 and aggregate["missing"] == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
