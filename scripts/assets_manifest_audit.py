#!/usr/bin/env python3
"""Assets-manifest reconciliation (P-027 RF source assets) - multi-namespace, single source.

Gates every ``test_data/assets/<namespace>/manifest.json`` - the machine-readable
fingerprint list consumed by ``verify_assets.py``. After the 2026-10-04 lifecycle
migration the hand-written ``MANIFEST.md`` was retired, so this check validates the
**manifest itself** (structure / presence / enums); the per-file SHA256 comparison
stays in ``verify_assets.py``. The two are complementary: structure vs content
fingerprint.

Namespaces are discovered by enumerating ``assets/*/`` (a new client is a new
directory), so adding a namespace needs no code change.

Checks (ERROR, fail-closed):
- ``assets/`` absent -> silent skip (local-only zone, CI-safe);
- every ``assets/<ns>/`` directory must contain a ``manifest.json`` (missing = ERROR);
- manifest is valid JSON, ``schema == 1`` and has a non-empty ``assets`` list;
- each ``path`` is a safe relative path, unique within the list, and the file
  exists on disk relative to the manifest;
- ``classification`` is one of ``client-confidential`` / ``public``.

Split out of ``audit_agent_ops.py`` so the orchestrator stays inside its line
budget (the ``docs_refs_audit.py`` / ``test_registry_audit.py`` pattern).

Standalone: ``python scripts/assets_manifest_audit.py``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_ROOT = REPO_ROOT / "test_data" / "assets"

CLASSIFICATIONS = ("client-confidential", "public")
SCHEMA_VERSION = 1


def is_valid_rel_path(p: str) -> bool:
    """Safe, non-escaping POSIX-style relative path."""
    if not p or p.startswith(("/", "\\")):
        return False
    parts = p.replace("\\", "/").split("/")
    return all(part not in ("", ".", "..") for part in parts)


def discover_namespaces() -> list[Path]:
    """Return ``assets/*/`` namespace directories (sorted); ``[]`` when absent."""
    if not ASSETS_ROOT.is_dir():
        return []
    return sorted(p for p in ASSETS_ROOT.iterdir() if p.is_dir())


def _check_one(ns_dir: Path, issues: list[dict]) -> None:
    """Validate one namespace; append ERROR issues (rel path = the manifest)."""
    manifest_path = ns_dir / "manifest.json"
    rel = manifest_path.relative_to(REPO_ROOT).as_posix()

    def bad(msg: str) -> None:
        issues.append({"check": "assets-manifest", "level": "ERROR",
                       "path": rel, "msg": msg})

    if not manifest_path.is_file():
        bad(f"manifest.json missing for namespace '{ns_dir.name}'")
        return

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        bad(f"cannot parse manifest.json: {exc}")
        return

    if data.get("schema") != SCHEMA_VERSION:
        bad(f"schema != {SCHEMA_VERSION}: {data.get('schema')!r}")

    assets = data.get("assets")
    if not isinstance(assets, list) or not assets:
        bad("assets must be a non-empty list")
        return

    seen: set[str] = set()
    for i, entry in enumerate(assets):
        if not isinstance(entry, dict):
            bad(f"assets[{i}] is not an object")
            continue
        path = entry.get("path")
        if not isinstance(path, str) or not is_valid_rel_path(path):
            bad(f"assets[{i}].path invalid: {path!r}")
            continue
        norm = path.replace("\\", "/")
        if norm in seen:
            bad(f"duplicate path: {norm}")
        seen.add(norm)
        if not (ns_dir / norm).is_file():
            bad(f"listed file missing on disk: {norm}")
        cls = entry.get("classification")
        if cls not in CLASSIFICATIONS:
            bad(f"assets[{i}].classification invalid: {cls!r} "
                f"(expected {CLASSIFICATIONS})")


def check_assets_manifest() -> list[dict]:
    """Validate every ``assets/*/manifest.json``; returns ERROR issues."""
    issues: list[dict] = []
    namespaces = discover_namespaces()
    if not namespaces:
        return issues  # local-only zone absent (CI-safe)
    for ns_dir in namespaces:
        _check_one(ns_dir, issues)
    return issues


def selftest_cases() -> list[tuple[str, bool]]:
    """Pure path validations (no repo facts)."""
    return [
        ("assets-path-ok",
         is_valid_rel_path("raw/a.pdf") and is_valid_rel_path("public/x.csv")),
        ("assets-path-parent", not is_valid_rel_path("../x")),
        ("assets-path-absolute",
         not is_valid_rel_path("/abs/x") and not is_valid_rel_path("\\abs")),
        ("assets-path-empty",
         not is_valid_rel_path("") and not is_valid_rel_path("a//b")),
    ]


def main() -> int:
    issues = check_assets_manifest()
    for i in issues:
        print(f"[ERROR] {i['path']}: {i['msg']}")
    print(f"[assets-manifest] {len(issues)} issue(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
