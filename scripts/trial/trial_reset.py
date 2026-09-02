"""Wipe trial data for a clean hand-off between prospects (GLM trial P0-1).

Deletes every uploaded file, output, debug artifact, and the queue-persistence
SQLite DB under the backend runtime dirs. In-memory task tables are NOT
flushed — restart the Pro server after running this for a fully clean state.

Usage (from backend/ cwd, or pass --root):
    python ../scripts/trial/trial_reset.py --yes          # wipe
    python ../scripts/trial/trial_reset.py --dry-run      # show what would go

Safety:
    - requires --yes (refuses otherwise)
    - aborts if the API answers on /health unless --force
    - removes directory CONTENTS, keeps the directories themselves
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

DEFAULT_ROOT = os.path.join("..", "..", "backend")

TARGETS = {
    "uploads": "uploaded client files",
    "outputs": "analysis results, figure crops, GT reports",
    "debug": "debug artifacts (DEBUG_MODE)",
    os.path.join("data"): "SQLite queue persistence (batch + HITL)",
}


def _count_dir(path: str) -> int:
    if not os.path.isdir(path):
        return 0
    return sum(len(files) for _, _, files in os.walk(path))


def _server_running(port: int) -> bool:
    try:
        import urllib.request

        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
        return True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Wipe DocuVision trial data (GLM trial)")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="backend root (default ../../backend from scripts/trial)")
    parser.add_argument("--yes", action="store_true", help="actually delete (required)")
    parser.add_argument("--dry-run", action="store_true", help="list what would be deleted and exit")
    parser.add_argument("--force", action="store_true", help="wipe even when the API is running")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"[error] backend root not found: {root}")
        return 2

    if args.dry_run:
        for rel, desc in TARGETS.items():
            path = os.path.join(root, rel)
            print(f"[dry-run] {rel:<8} {_count_dir(path):>5} files — {desc}")
        return 0

    if not args.yes:
        print("[refuse] pass --yes to wipe, or --dry-run to preview. No action taken.")
        return 2

    if _server_running(args.port) and not args.force:
        print(f"[refuse] API is live on :{args.port}. Stop the server or pass --force.")
        return 2

    deleted = 0
    for rel, desc in TARGETS.items():
        path = os.path.join(root, rel)
        if not os.path.isdir(path):
            continue
        for entry in os.listdir(path):
            entry_path = os.path.join(path, entry)
            try:
                if os.path.isdir(entry_path) and not os.path.islink(entry_path):
                    shutil.rmtree(entry_path)
                else:
                    os.remove(entry_path)
                deleted += 1
            except OSError as exc:
                print(f"[warn] could not remove {entry_path}: {exc}")
        print(f"[ok] cleared {rel:<8} ({desc})")

    print(f"[done] {deleted} entries removed. Restart the Pro server for a fully clean state.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
