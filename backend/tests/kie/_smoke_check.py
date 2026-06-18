"""Lightweight KIE subpackage smoke (no model weights).

Delegates to the canonical pytest suite for ``value_typer`` so assertions
are not duplicated here.

Run from ``backend/``:

    python -m tests.kie._smoke_check
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    backend_dir = Path(__file__).resolve().parents[2]
    target = backend_dir / "tests" / "kie" / "test_value_typer.py"
    print(f"[smoke] running pytest on {target.relative_to(backend_dir)}")
    return subprocess.call(
        [sys.executable, "-m", "pytest", str(target), "-q"],
        cwd=str(backend_dir),
    )


if __name__ == "__main__":
    raise SystemExit(main())
