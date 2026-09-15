#!/usr/bin/env python3
"""File-size gate (v1.8.2 C5) - stdlib only; never imports application code.

Enforces the rules in DEVELOPMENT.md / v1.8.2 design section 6:

  R-a  a non-allowlisted file over ``budget`` physical lines          -> violation
  R-b  an allowlisted file over its recorded (ratchet) line count     -> violation
  R-c  ``backend/app/main.py`` declaring an ``@app.<method>`` route   -> violation

Scope: tracked ``.py`` files under ``backend/app/`` and ``scripts/`` (tests are
exempt). Enumerating via git keeps a local run identical to CI and avoids
flagging untracked scratch files; when git is unavailable the script falls back
to a filesystem walk.

Line counts use ``str.splitlines()`` - physical lines including blanks and
comments, i.e. the same number as ``wc -l`` for newline-terminated files.

Ratchet: ``python scripts/lint_file_size.py --update`` rewrites the allowlist
down to the current, smaller counts. CI never passes ``--update``.

Exit codes: 0 = pass, 1 = violations, 2 = cannot evaluate.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST = REPO_ROOT / "scripts" / "file_size_allowlist.json"
SCAN_ROOTS = ("backend/app", "scripts")
DEFAULT_BUDGET = 500
MAIN = "backend/app/main.py"

_ROUTE_DECORATOR = re.compile(r"@app\.(get|post|put|delete|patch|websocket)\(")


def _count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _tracked_py_files() -> tuple[list[Path], str]:
    """Return (files, mode): git-tracked .py under SCAN_ROOTS, else fs walk."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--", *SCAN_ROOTS],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        rel = [p for p in proc.stdout.split("\0") if p.endswith(".py")]
        return [REPO_ROOT / p for p in rel], "git"
    except Exception:
        files: list[Path] = []
        for root in SCAN_ROOTS:
            base = REPO_ROOT / root
            if base.is_dir():
                files.extend(
                    p for p in base.rglob("*.py") if "__pycache__" not in p.parts
                )
        return files, "fs"


def _load_allowlist() -> dict:
    if not ALLOWLIST.is_file():
        print(f"[lint_file_size] allowlist not found: {ALLOWLIST}", file=sys.stderr)
        raise SystemExit(2)
    data = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    data.setdefault("budget", DEFAULT_BUDGET)
    data.setdefault("files", {})
    return data


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _route_decorators_in_main(files: list[Path]) -> list[str]:
    for path in files:
        if _rel(path) != MAIN:
            continue
        text = path.read_text(encoding="utf-8")
        return [
            f"{MAIN}:{lineno}  route decorator outside routers/ (D7)"
            for lineno, line in enumerate(text.splitlines(), 1)
            if _ROUTE_DECORATOR.search(line)
        ]
    return []


def _update(allowlist: dict, counts: dict[str, int]) -> int:
    lowered = False
    for key, recorded in sorted(allowlist["files"].items()):
        actual = counts.get(key)
        if actual is not None and actual < recorded:
            allowlist["files"][key] = actual
            lowered = True
            print(f"[lowered] {key}: {recorded} -> {actual}")
    ALLOWLIST.write_text(
        json.dumps(allowlist, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"[lint_file_size] allowlist {'updated' if lowered else 'unchanged'}")
    return 0


def main(argv: list[str]) -> int:
    allowlist = _load_allowlist()
    budget = int(allowlist["budget"])
    recorded = dict(allowlist["files"])

    files, mode = _tracked_py_files()
    counts = {_rel(p): _count_lines(p) for p in files if p.is_file()}

    if "--update" in argv:
        return _update(allowlist, counts)

    violations: list[str] = []
    for key, n in sorted(counts.items()):
        cap = recorded.get(key)
        if cap is None:
            if n > budget:
                violations.append(f"{key}: {n} lines > budget {budget}")
        elif n > cap:
            violations.append(f"{key}: {n} lines > allowlist {cap}")

    violations.extend(_route_decorators_in_main(files))

    print(
        f"[lint_file_size] scanned {len(counts)} tracked .py file(s) "
        f"(mode={mode}, budget={budget})"
    )
    if violations:
        for v in violations:
            print(f"[FAIL] {v}")
        print(f"[lint_file_size] {len(violations)} violation(s)")
        return 1
    print("[lint_file_size] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
