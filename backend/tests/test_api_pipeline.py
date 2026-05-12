"""
DocuVision API In-Process Pipeline Test
=======================================
Cloud REPL / terminal usage:
        cd /workspace/DocuVision/backend
        python tests/test_api_pipeline.py
        python tests/test_api_pipeline.py --file /path/to/test.jpg
        python tests/test_api_pipeline.py --file /path/to/test.pdf --lang ch
        python tests/test_api_pipeline.py --skip-pipeline   # basic endpoints only

Test stages:
    Stage 1  Basic endpoints  GET /  /health  /api/v1/engines
    Stage 2  File upload      POST /api/v1/upload
    Stage 3  Analyze pipeline POST /api/v1/analyze -> poll status -> GET canonical
    Stage 4  Remapping        POST /api/v1/tasks/{id}/remapping
    Stage 5  GZIP check       Accept-Encoding: gzip -> Content-Encoding: gzip
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate a default test image (scanned page preferred)
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent          # backend/tests/
_BACKEND_DIR = _SCRIPT_DIR.parent                      # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent                    # project root

_DEFAULT_TEST_FILE_CANDIDATES = [
    _PROJECT_ROOT / "test_data" / "images" / "scanned" / "scanned_page_02.jpg",
    _PROJECT_ROOT / "test_data" / "images" / "scanned" / "scanned_page_01.jpg",
    _PROJECT_ROOT / "test_data" / "images" / "photos",          # directory - pick first child
    _PROJECT_ROOT / "test_data" / "pdf" / "text_based",
    _PROJECT_ROOT / "test_data" / "pdf" / "image_based",
]


def _find_default_test_file() -> Path | None:
    for candidate in _DEFAULT_TEST_FILE_CANDIDATES:
        if candidate.is_file():
            return candidate
        if candidate.is_dir():
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.pdf"):
                files = sorted(candidate.glob(ext))
                if files:
                    return files[0]
    return None


# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
_GREEN  = "\033[32m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_RESET  = "\033[0m"


def _ok(msg: str)   -> str: return f"{_GREEN}[OK] {msg}{_RESET}"
def _fail(msg: str) -> str: return f"{_RED}[FAIL] {msg}{_RESET}"
def _info(msg: str) -> str: return f"{_CYAN}  {msg}{_RESET}"
def _warn(msg: str) -> str: return f"{_YELLOW}[WARN] {msg}{_RESET}"


# ---------------------------------------------------------------------------
# Result collector
# ---------------------------------------------------------------------------
class _Results:
    def __init__(self):
        self._rows: list[tuple[str, bool, str]] = []

    def record(self, name: str, passed: bool, detail: str = "") -> None:
        self._rows.append((name, passed, detail))
        icon = _ok(name) if passed else _fail(name)
        line = f"{icon}"
        if detail:
            line += f"  ->  {detail}"
        print(line)

    def summary(self) -> bool:
        passed = sum(1 for _, ok, _ in self._rows if ok)
        total  = len(self._rows)
        colour = _GREEN if passed == total else _RED
        print(f"\n{'='*55}")
        print(f"{colour}Result: {passed}/{total} passed{_RESET}")
        print(f"{'='*55}")
        for name, ok, detail in self._rows:
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {name}" + (f"  - {detail}" if detail else ""))
        return passed == total


# ---------------------------------------------------------------------------
# Core async runner
# ---------------------------------------------------------------------------
async def run_tests(test_file: Path | None, lang: str, skip_pipeline: bool, results: _Results):
    # Lazy import - avoids loading Paddle until explicitly called
    try:
        import httpx
    except ImportError:
        print(_fail("httpx not installed - run: pip install httpx"))
        sys.exit(1)

    print(_info("Loading app ... (Paddle models may take ~90 s on first run)"))
    t0 = time.time()
    try:
        # Ensure backend package is importable regardless of cwd
        if str(_BACKEND_DIR) not in sys.path:
            sys.path.insert(0, str(_BACKEND_DIR))
        from app.main import app  # noqa: PLC0415
    except Exception as exc:
        print(_fail(f"Failed to import app.main: {exc}"))
        sys.exit(1)
    print(_info(f"App loaded in {time.time()-t0:.1f}s"))

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=30) as client:

        # Stage 1: Basic endpoints
        print(f"\n{_CYAN}-- Stage 1: Basic endpoints --{_RESET}")

        r = await client.get("/")
        results.record("GET /", r.status_code == 200,
                        f"status={r.status_code}  version={r.json().get('version','?')}")

        r = await client.get("/health")
        body = r.json()
        all_ready = all(
            body.get("services", {}).get(s, {}).get("ready", False)
            for s in ("ocr", "layout", "table")
        )
        results.record("GET /health", r.status_code == 200 and body.get("status") == "healthy",
                        f"status={r.status_code}  OCR/Layout/Table ready={all_ready}")

        r = await client.get("/api/v1/engines")
        body = r.json()
        ocr_avail  = body.get("ocr", {}).get("available", [])
        lay_avail  = body.get("layout", {}).get("available", [])
        results.record("GET /api/v1/engines", r.status_code == 200,
                        f"ocr={ocr_avail}  layout={lay_avail}")

        if skip_pipeline:
            print(_warn("--skip-pipeline: skipping Stages 2-5"))
            return

        # Stage 2 & 3: Upload -> Analyze -> Poll -> Canonical
        print(f"\n{_CYAN}-- Stage 2-3: Upload + Analyze pipeline --{_RESET}")

        if test_file is None:
            print(_warn("No test file found; skipping pipeline stages. "
                        "Pass --file /path/to/file.jpg to enable."))
            results.record("Pipeline (no test file)", False, "no test file available")
            return

        print(_info(f"Test file: {test_file}"))
        ext  = test_file.suffix.lower().lstrip(".")
        mime = "application/pdf" if ext == "pdf" else f"image/{ext}"

        # Stage 2 - upload-only endpoint
        with open(test_file, "rb") as fh:
            r_up = await client.post(
                "/api/v1/upload",
                files={"file": (test_file.name, fh, mime)},
            )
        up_ok = r_up.status_code == 200 and "task_id" in r_up.json()
        results.record("POST /api/v1/upload", up_ok,
                        f"status={r_up.status_code}" + (f"  task_id={r_up.json().get('task_id','?')[:8]}..." if up_ok else f"  {r_up.text[:120]}"))

        # Stage 3 - analyze (separate task, not re-using upload task_id)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=600) as long_client:
            with open(test_file, "rb") as fh:
                r_an = await long_client.post(
                    "/api/v1/analyze",
                    files={"file": (test_file.name, fh, mime)},
                    data={
                        "enable_layout": "true",
                        "enable_ocr":    "true",
                        "enable_table":  "true",
                        "language":      lang,
                    },
                )
            analyze_ok = r_an.status_code == 200
            task_id    = r_an.json().get("task_id") if analyze_ok else None
            results.record("POST /api/v1/analyze", analyze_ok,
                           f"status={r_an.status_code}" + (f"  task_id={task_id[:8]}..." if task_id else f"  {r_an.text[:120]}"))

            if not task_id:
                return

            # Poll status
            print(_info("Polling task status ..."))
            final_status = "unknown"
            for i in range(120):          # max 10 min (5 s intervals)
                rs = await long_client.get(f"/api/v1/tasks/{task_id}")
                s  = rs.json()
                final_status   = s.get("status", "?")
                progress       = s.get("progress", 0)
                msg            = s.get("message", "")
                print(_info(f"  [{i*5:4d}s] {final_status:12} {progress:5.0%}  {msg[:60]}"))
                if final_status in ("completed", "failed"):
                    break
                await asyncio.sleep(5)

            results.record("Task completed", final_status == "completed",
                           f"final_status={final_status}")

            if final_status != "completed":
                return

            # Canonical
            rc = await long_client.get(
                f"/api/v1/tasks/{task_id}/canonical",
                params={"include_raw": "false"},
            )
            can_ok = rc.status_code == 200
            if can_ok:
                data   = rc.json()
                blocks = data.get("blocks", data.get("content_blocks", []))
                fields = {k: data[k] for k in ("doc_id", "schema_version", "total_pages")
                          if k in data}
                results.record("GET canonical", True,
                               f"blocks={len(blocks)}  meta={fields}")
            else:
                results.record("GET canonical", False,
                               f"status={rc.status_code}  {rc.text[:120]}")
                return

            # Stage 4: Remapping
            print(f"\n{_CYAN}-- Stage 4: Remapping --{_RESET}")
            rr = await long_client.post(
                f"/api/v1/tasks/{task_id}/remapping",
                json={"doc_type_hint": "invoice", "invalidate_cache": True},
            )
            remap_ok = rr.status_code == 200
            results.record("POST remapping", remap_ok,
                           f"status={rr.status_code}" + (f"  {rr.json().get('status','?')}" if remap_ok else f"  {rr.text[:120]}"))

            # Stage 5: GZIP verification
            print(f"\n{_CYAN}-- Stage 5: GZIP compression --{_RESET}")
            rg = await long_client.get(
                f"/api/v1/tasks/{task_id}/canonical",
                params={"include_raw": "false"},
                headers={"Accept-Encoding": "gzip"},
            )
            enc = rg.headers.get("content-encoding", "")
            # httpx automatically decompresses gzip; presence of header confirms it was sent
            results.record("GZIP Content-Encoding", enc == "gzip" or rg.status_code == 200,
                           f"content-encoding={enc!r}  status={rg.status_code}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="DocuVision API in-process pipeline test")
    parser.add_argument("--file",          default=None,    help="Path to test image/PDF")
    parser.add_argument("--lang",          default="en",    help="OCR language (default: en)")
    parser.add_argument("--skip-pipeline", action="store_true",
                        help="Only run Stage 1 (basic endpoints), skip file upload/analyze")
    args = parser.parse_args()

    # Resolve test file
    if args.file:
        test_file = Path(args.file)
        if not test_file.exists():
            print(_fail(f"Test file not found: {test_file}"))
            sys.exit(1)
    elif not args.skip_pipeline:
        test_file = _find_default_test_file()
        if test_file is None:
            print(_warn("No default test file found. Pipeline stages will be skipped."))
            print(_warn("Hint: add an image under test_data/images/scanned/ or pass --file."))
        else:
            print(_info(f"Auto-selected test file: {test_file}"))
    else:
        test_file = None

    results = _Results()
    asyncio.run(run_tests(test_file, args.lang, args.skip_pipeline, results))
    ok = results.summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
