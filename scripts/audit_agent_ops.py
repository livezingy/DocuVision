#!/usr/bin/env python3
"""Unified agent-ops audit: kernel-ref drift + living-doc drift.

Two checks in one framework (per the agent-ops refactor plan):

1. agent rules drift: every generated agent copy must match its kernel
   sources. Compared by re-rendering from the kernel and diffing against the
   on-disk copy (same logic as `sync_agent_rules.py --check`).

2. living-doc drift: file paths referenced by living docs
   (`docs/architecture/*.md`, `docs/README.md`) must exist in the repo. This
   catches docs pointing at renamed/removed modules. References to
   runtime-generated artifacts (DOC_DRIFT_ALLOW_PREFIXES, e.g. the gitignored
   backend/debug/) are exempt.

Severity:
  - agent rules drift  -> ERROR (exit 1, hard gate for PR->main CI)
  - living-doc drift   -> WARN  (reported, does not fail the gate by default)

Usage:
    python scripts/audit_agent_ops.py            # both checks
    python scripts/audit_agent_ops.py --json     # machine-readable output

Exit code: 1 if any ERROR, else 0.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import sync_agent_rules as sync_mod  # noqa: E402

REPO_ROOT = sync_mod.REPO_ROOT

LIVING_DOC_GLOBS = [
    "docs/architecture/*.md",
    "docs/README.md",
]

# File path references inside docs, e.g. backend/app/services/export_service.py
PATH_REF_RE = re.compile(
    r"\b(?:backend|apps|packages|frontend|supabase)/[A-Za-z0-9_/.\-]+"
    r"\.(?:py|js|ts|tsx|jsx|md|json|yaml|yml|sql|ps1|sh)\b"
)

# Strip a trailing ":<lineno>" and drop glob patterns (contain *).
GLOB_CHARS = ("*", "?")
LINE_REF_RE = re.compile(r":\d+$")

# Path prefixes pointing at runtime-generated artifacts (mirrors .gitignore,
# e.g. backend/debug/): valid doc references even though the files never
# exist in a fresh clone. Keep this list narrow.
DOC_DRIFT_ALLOW_PREFIXES = ("backend/debug/",)


def _norm_ref(ref: str) -> str | None:
    ref = LINE_REF_RE.sub("", ref)
    if any(ch in ref for ch in GLOB_CHARS) or "..." in ref:
        return None
    return ref


def check_agent_rules() -> list[dict]:
    """Re-render each agent copy and compare to disk. Returns ERROR issues."""
    issues: list[dict] = []
    for agent, cfg in sync_mod.AGENTS.items():
        for spec in cfg["files"]:
            out_path = cfg["dir"] / spec["out"]
            if not out_path.exists():
                issues.append({
                    "check": "agent-rules", "level": "ERROR",
                    "path": str(out_path.relative_to(REPO_ROOT)),
                    "msg": "generated copy missing; run scripts/sync_agent_rules.py",
                })
                continue
            expected = sync_mod.render(spec)
            actual = out_path.read_text(encoding="utf-8")
            if actual != expected:
                issues.append({
                    "check": "agent-rules", "level": "ERROR",
                    "path": str(out_path.relative_to(REPO_ROOT)),
                    "msg": "copy differs from kernel; run scripts/sync_agent_rules.py",
                })
    return issues


def check_doc_drift() -> list[dict]:
    """Report file paths referenced by living docs that do not exist."""
    issues: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for glob in LIVING_DOC_GLOBS:
        for doc in sorted(REPO_ROOT.glob(glob)):
            text = doc.read_text(encoding="utf-8")
            for m in PATH_REF_RE.finditer(text):
                ref = _norm_ref(m.group(0))
                if ref is None or ref.startswith(DOC_DRIFT_ALLOW_PREFIXES):
                    continue
                key = (str(doc.relative_to(REPO_ROOT)), ref)
                if key in seen:
                    continue
                seen.add(key)
                if not (REPO_ROOT / ref).exists():
                    issues.append({
                        "check": "doc-drift", "level": "WARN",
                        "path": str(doc.relative_to(REPO_ROOT)),
                        "msg": f"referenced path missing: {ref}",
                    })
    return issues


def main() -> int:
    as_json = "--json" in sys.argv[1:]
    issues = check_agent_rules() + check_doc_drift()

    if as_json:
        payload = {
            "checked_at": datetime.now().isoformat(),
            "ok": not any(i["level"] == "ERROR" for i in issues),
            "errors": [i for i in issues if i["level"] == "ERROR"],
            "warnings": [i for i in issues if i["level"] == "WARN"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        errors = [i for i in issues if i["level"] == "ERROR"]
        warnings = [i for i in issues if i["level"] == "WARN"]
        print(f"[AUDIT] {datetime.now():%Y-%m-%d %H:%M} "
              f"{len(errors)} error(s), {len(warnings)} warning(s)")
        for i in errors:
            print(f"  [ERROR] {i['path']}: {i['msg']}")
        for i in warnings:
            print(f"  [WARN]  {i['path']}: {i['msg']}")
        if not issues:
            print("[AUDIT] all checks passed")

    return 1 if any(i["level"] == "ERROR" for i in issues) else 0


if __name__ == "__main__":
    sys.exit(main())
