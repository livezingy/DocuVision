#!/usr/bin/env python3
"""Commit-message gate (P-042 T1) - lint commit subjects against the type enum.

Validates each commit subject against the type enum defined in
``.cursor/rules/003-git.mdc`` (:9 format sample, :11-20 enum) - that file is
the true source; do not extend or shrink the enum here. Merge/Revert
auto-generated subjects are exempt and printed as [SKIP] (still counted).

Usage:
    python scripts/lint_commit_msgs.py --range <base>..<head>   # CI: via git log
    python scripts/lint_commit_msgs.py --stdin                  # local: one subject per line

Per line: ``[OK]/[FAIL]/[SKIP] <subject truncated to 60 chars>``; last line
``scanned N commit(s), M violation(s)``. Description language/length/tone are
conventions (003-git 重要原则), deliberately NOT gated here.

Exit codes: 0 = pass (or zero input: prints "no commits to scan"),
1 = violations found, 2 = cannot evaluate (bad usage / git log failure).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# True source: .cursor/rules/003-git.mdc :9 (format) / :11-20 (10-type enum).
# type must be lowercase, ASCII colon, exactly one space, non-empty description.
_COMMIT_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|chore|revert|build): \S.*"
)
# Exempt auto-generated subjects; "^Merge " covers "^Merge pull request ..."
# (the pack lists the latter only to disambiguate).
_EXEMPT_RE = re.compile(r"^(Merge |Revert )")


def _subjects_from_range(spec: str) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "log", "--format=%s", spec],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(
            f"[lint_commit_msgs] git log failed: {proc.stderr.strip()}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def main(argv: list[str]) -> int:
    subjects: list[str]
    if len(argv) == 2 and argv[0] == "--range":
        subjects = _subjects_from_range(argv[1])
    elif len(argv) == 1 and argv[0] == "--stdin":
        subjects = [line for line in sys.stdin.read().splitlines() if line.strip()]
    else:
        print(
            "usage: lint_commit_msgs.py --range <base>..<head> | --stdin",
            file=sys.stderr,
        )
        return 2

    if not subjects:
        print("no commits to scan")
        return 0

    violations = 0
    for subject in subjects:
        if _EXEMPT_RE.match(subject):
            print(f"[SKIP] {subject[:60]}")
        elif _COMMIT_RE.match(subject):
            print(f"[OK] {subject[:60]}")
        else:
            print(f"[FAIL] {subject[:60]}")
            violations += 1
    print(f"scanned {len(subjects)} commit(s), {violations} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
