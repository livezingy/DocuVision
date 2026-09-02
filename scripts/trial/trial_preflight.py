"""Trial preflight: verify the environment before the 60-minute call (GLM trial P1).

Run this ~30 minutes before the trial from the machine hosting the Pro
server (Cloud Studio). Every check prints [OK]/[WARN]/[FAIL]; the script
exits non-zero when any FAIL remains, so it doubles as a gate.

Usage (from backend/ cwd on the server host):
    python ../scripts/trial/trial_preflight.py [--base http://127.0.0.1:8000]

Checks:
    A. /health reachable, KIE model loaded, OCR ready
    B. trial sample files present (test_data/testfiles/trial/)
    C. API key configured (backend/.env DOCUVISION_TRIAL_API_KEY non-empty)
    D. CORS allowlist configured when a public origin is used
    E. free disk space above threshold
    F. SQLite queue store writable
    G. uploads/outputs dirs writable
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.request

FAILURES = 0
WARNINGS = 0

SAMPLES = [
    "multi_column_techdoc.pdf",
    "flowchart_page.pdf",
    "architecture_diagram.pdf",
]


def _report(level: str, label: str, detail: str = "") -> None:
    global FAILURES, WARNINGS
    mark = {"OK": "[OK]  ", "WARN": "[WARN]", "FAIL": "[FAIL]"}[level]
    print(f"{mark} {label}{(' — ' + detail) if detail else ''}")
    if level == "FAIL":
        FAILURES += 1
    elif level == "WARN":
        WARNINGS += 1


def _get_json(url: str, timeout: int = 8):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="DocuVision trial preflight (GLM)")
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="Pro API base URL")
    parser.add_argument("--root", default=".", help="backend root (default: cwd)")
    parser.add_argument("--samples-root", default="", help="override trial samples dir")
    parser.add_argument("--min-free-gb", type=float, default=5.0)
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    samples_root = os.path.abspath(
        args.samples_root
        or os.path.join("..", "test_data", "testfiles", "trial")
    )

    print(f"== DocuVision trial preflight ==\nroot={root}\nbase={args.base}\n")

    # A. health + engines
    try:
        health = _get_json(f"{args.base}/health")
        _report("OK", "API /health reachable", f"api_version={health.get('api_version')}")
        kie = health.get("kie") or {}
        if kie.get("model_loaded"):
            _report("OK", "KIE model loaded", str(kie.get("model_id", "")))
        else:
            _report("FAIL", "KIE model not loaded", "set DOCUVISION_KIE_WARMUP=1 and wait, or skip KIE demos")
        ocr = (health.get("services") or {}).get("ocr") or {}
        if ocr.get("ready"):
            _report("OK", "OCR service ready")
        else:
            _report("WARN", "OCR service not ready", str(ocr.get("engines", "")))
    except Exception as exc:
        _report("FAIL", "API /health unreachable", str(exc))

    # B. trial samples
    for name in SAMPLES:
        path = os.path.join(samples_root, name)
        if os.path.isfile(path) and os.path.getsize(path) > 1024:
            _report("OK", f"sample {name}")
        else:
            _report("FAIL", f"sample {name} missing", f"run scripts/trial/generate_trial_samples.py (expected at {path})")

    # C. API key
    env_path = os.path.join(root, ".env")
    key_found = False
    if os.path.isfile(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line.startswith(("DOCUVISION_TRIAL_API_KEY=", "TRIAL_API_KEY=")) and line.split("=", 1)[1].strip():
                key_found = True
    if key_found:
        _report("OK", "trial API key configured (backend/.env)")
    elif os.environ.get("DOCUVISION_TRIAL_API_KEY") or os.environ.get("TRIAL_API_KEY"):
        _report("OK", "trial API key configured (environment)")
    else:
        _report("WARN", "trial API key not configured", "remote trials should set DOCUVISION_TRIAL_API_KEY in backend/.env")

    # D. CORS allowlist
    if os.path.isfile(env_path):
        for line in open(env_path, encoding="utf-8"):
            if line.strip().startswith(("DOCUVISION_CORS_ORIGINS=", "CORS_ORIGINS=")):
                val = line.split("=", 1)[1].strip()
                if val and val != '"*"':
                    _report("OK", "CORS allowlist configured")
                else:
                    _report("WARN", "CORS wide open (*)", "set DOCUVISION_CORS_ORIGINS for remote trials")
                break

    # E. disk space
    try:
        free_gb = shutil.disk_usage(root).free / (1024 ** 3)
        if free_gb >= args.min_free_gb:
            _report("OK", f"free disk {free_gb:.1f} GB")
        else:
            _report("WARN", f"free disk {free_gb:.1f} GB", f"below {args.min_free_gb} GB — model caches may fail")
    except OSError as exc:
        _report("WARN", "disk check failed", str(exc))

    # F. SQLite writable
    db = os.path.join(root, "data", "docuvision.sqlite")
    try:
        os.makedirs(os.path.dirname(db), exist_ok=True)
        probe = db + ".preflight_probe"
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        _report("OK", "SQLite store dir writable")
    except OSError as exc:
        _report("FAIL", "SQLite store dir not writable", str(exc))

    # G. runtime dirs writable
    for rel in ("uploads", "outputs"):
        path = os.path.join(root, rel)
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".preflight_probe")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            _report("OK", f"{rel}/ writable")
        except OSError as exc:
            _report("FAIL", f"{rel}/ not writable", str(exc))

    print(f"\n== summary: {FAILURES} failure(s), {WARNINGS} warning(s) ==")
    if FAILURES:
        print("Fix the FAIL items before the trial. WARN items are acceptable with a plan.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
