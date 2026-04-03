"""
DocuVision API Contract Smoke Test (Cloud Runnable)
===================================================
Purpose:
- Fast API contract checks for status codes and response shapes
- Focus on lifecycle/error-path endpoints that do not require full OCR completion

Usage:
    cd /workspace/DocuVision/backend
    python tests/test_api_contract_smoke.py
    python tests/test_api_contract_smoke.py --file /workspace/DocuVision/test_data/images/scanned/scanned_page_02.jpg

Notes:
- This script runs in-process with httpx.ASGITransport (no external server required).
- Optional --file enables upload/cancel/delete lifecycle checks.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
import uuid
from pathlib import Path


_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
_PROJECT_ROOT = _BACKEND_DIR.parent

_DEFAULT_TEST_FILE_CANDIDATES = [
    _PROJECT_ROOT / "test_data" / "images" / "scanned" / "scanned_page_02.jpg",
    _PROJECT_ROOT / "test_data" / "images" / "scanned" / "scanned_page_01.jpg",
    _PROJECT_ROOT / "test_data" / "images" / "photos",
    _PROJECT_ROOT / "test_data" / "pdf" / "image_based",
]


_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_RESET = "\033[0m"


def _ok(msg: str) -> str:
    return f"{_GREEN}[OK] {msg}{_RESET}"


def _fail(msg: str) -> str:
    return f"{_RED}[FAIL] {msg}{_RESET}"


def _warn(msg: str) -> str:
    return f"{_YELLOW}[WARN] {msg}{_RESET}"


def _info(msg: str) -> str:
    return f"{_CYAN}{msg}{_RESET}"


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


class Results:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.rows.append((name, passed, detail))
        head = _ok(name) if passed else _fail(name)
        if detail:
            print(f"{head} -> {detail}")
        else:
            print(head)

    def done(self) -> bool:
        passed = sum(1 for _, ok, _ in self.rows if ok)
        total = len(self.rows)
        color = _GREEN if passed == total else _RED
        print("\n" + "=" * 60)
        print(f"{color}Summary: {passed}/{total} passed{_RESET}")
        print("=" * 60)
        for name, ok, detail in self.rows:
            mark = "PASS" if ok else "FAIL"
            extra = f" - {detail}" if detail else ""
            print(f"[{mark}] {name}{extra}")
        return passed == total


def _json_or_text(resp) -> str:
    try:
        return str(resp.json())
    except Exception:
        return (resp.text or "")[:160]


async def run_contract_checks(test_file: Path | None, res: Results) -> None:
    try:
        import httpx
    except ImportError:
        print(_fail("httpx not installed. Run: pip install httpx"))
        sys.exit(1)

    print(_info("Loading app.main ..."))
    t0 = time.time()
    if str(_BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(_BACKEND_DIR))

    try:
        from app.main import app  # noqa: PLC0415
    except Exception as exc:
        print(_fail(f"Failed to import app.main: {exc}"))
        sys.exit(1)

    print(_info(f"App loaded in {time.time() - t0:.1f}s"))

    transport = httpx.ASGITransport(app=app)
    fake_task_id = f"missing-{uuid.uuid4().hex[:12]}"

    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60) as client:
        print(_info("\nStage A: Basic service and discovery endpoints"))

        r = await client.get("/")
        res.add("GET /", r.status_code == 200, f"status={r.status_code}")

        r = await client.get("/health")
        status = None
        try:
            status = r.json().get("status")
        except Exception:
            status = None
        res.add("GET /health", r.status_code == 200 and status == "healthy", f"status={r.status_code} body_status={status}")

        r = await client.get("/api/v1/engines")
        has_ocr = False
        try:
            has_ocr = "ocr" in r.json()
        except Exception:
            has_ocr = False
        res.add("GET /api/v1/engines", r.status_code == 200 and has_ocr, f"status={r.status_code}")

        print(_info("\nStage B: Task endpoints error-path contract"))

        r = await client.get(f"/api/v1/tasks/{fake_task_id}")
        res.add("GET missing task", r.status_code == 404, f"status={r.status_code}")

        r = await client.get(f"/api/v1/tasks/{fake_task_id}/result")
        res.add("GET missing task result", r.status_code == 404, f"status={r.status_code}")

        r = await client.get(f"/api/v1/tasks/{fake_task_id}/canonical")
        res.add("GET missing canonical", r.status_code == 404, f"status={r.status_code}")

        r = await client.post(
            f"/api/v1/tasks/{fake_task_id}/remapping",
            json={"doc_type_hint": "invoice", "invalidate_cache": True},
        )
        res.add("POST remap missing task", r.status_code == 404, f"status={r.status_code}")

        r = await client.post(f"/api/v1/tasks/{fake_task_id}/cancel")
        res.add("POST cancel missing task", r.status_code == 404, f"status={r.status_code}")

        r = await client.delete(f"/api/v1/tasks/{fake_task_id}")
        res.add("DELETE missing task", r.status_code == 404, f"status={r.status_code}")

        r = await client.get(f"/api/v1/tasks/{fake_task_id}/events")
        ok = r.status_code == 200 and isinstance(r.json().get("events", []), list)
        res.add("GET missing task events", ok, f"status={r.status_code} events_len={len(r.json().get('events', []))}")

        print(_info("\nStage B2: Phase 1 Job endpoints error-path contract"))

        fake_job_id = f"missing-{uuid.uuid4().hex[:12]}"

        r = await client.get(f"/api/v1/jobs/{fake_job_id}")
        res.add("GET missing job", r.status_code == 404, f"status={r.status_code}")

        r = await client.get(f"/api/v1/jobs/{fake_job_id}/result")
        res.add("GET missing job result", r.status_code == 404, f"status={r.status_code}")

        r = await client.get(f"/api/v1/jobs/{fake_job_id}/debug")
        # Debug endpoint returns 404 for both missing job AND when DEBUG_MODE=false
        res.add("GET missing job debug (should 404)", r.status_code == 404, f"status={r.status_code}")

        print(_info("\nStage C: Template/NLP service contract"))

        r = await client.get("/api/v1/templates")
        ok = r.status_code == 410
        res.add("GET /api/v1/templates", ok, f"status={r.status_code}")

        missing_template = f"tpl-{uuid.uuid4().hex[:10]}"
        r = await client.get(f"/api/v1/templates/{missing_template}")
        res.add("GET missing template", r.status_code == 410, f"status={r.status_code}")

        r = await client.post("/api/v1/templates/match", data={"text": "Invoice No. 1001 Total 123.45"})
        ok = r.status_code == 410
        res.add("POST /api/v1/templates/match", ok, f"status={r.status_code}")

        r = await client.post("/api/v1/nlp/keywords", json={"text": "hello world", "top_k_keywords": 5})
        res.add("POST /api/v1/nlp/keywords", r.status_code == 410, f"status={r.status_code}")

        r = await client.post("/api/v1/nlp/entities", json={"text": "John in New York"})
        res.add("POST /api/v1/nlp/entities", r.status_code == 410, f"status={r.status_code}")

        if not test_file:
            print(_warn("No --file provided and no default test file found. Skipping upload lifecycle checks."))
            return

        print(_info("\nStage D: Upload/cancel/delete lifecycle (fast path)"))
        print(_info(f"Using test file: {test_file}"))

        ext = test_file.suffix.lower().lstrip(".")
        mime = "application/pdf" if ext == "pdf" else f"image/{ext}"

        with open(test_file, "rb") as fh:
            r = await client.post("/api/v1/upload", files={"file": (test_file.name, fh, mime)})
        upload_ok = r.status_code == 200 and "task_id" in r.json()
        upload_task_id = r.json().get("task_id") if upload_ok else None
        res.add("POST /api/v1/upload", upload_ok, f"status={r.status_code}")

        if not upload_task_id:
            return

        r = await client.get(f"/api/v1/tasks/{upload_task_id}")
        st = r.json().get("status") if r.status_code == 200 else "?"
        res.add("GET uploaded task", r.status_code == 200 and st in ("uploaded", "pending", "processing"), f"status={r.status_code} task_status={st}")

        r = await client.post(f"/api/v1/tasks/{upload_task_id}/cancel")
        res.add("POST cancel uploaded task", r.status_code == 200, f"status={r.status_code} body={_json_or_text(r)}")

        r = await client.delete(f"/api/v1/tasks/{upload_task_id}")
        res.add("DELETE uploaded task", r.status_code == 200, f"status={r.status_code}")

        r = await client.get(f"/api/v1/tasks/{upload_task_id}")
        res.add("GET deleted task", r.status_code == 404, f"status={r.status_code}")

        print(_info("\nStage E: Phase 1 documents:analyze lifecycle"))

        ext = test_file.suffix.lower().lstrip(".")
        mime = "application/pdf" if ext == "pdf" else f"image/{ext}"

        with open(test_file, "rb") as fh:
            r = await client.post("/api/v1/documents:analyze", files={"file": (test_file.name, fh, mime)})
        analyze_ok = r.status_code == 200
        analyze_job_id = None
        if analyze_ok:
            try:
                job_data = r.json()
                analyze_job_id = job_data.get("job_id")
                has_status = job_data.get("status") in ("running", "pending", "succeeded")
                analyze_ok = analyze_job_id is not None and has_status
            except Exception:
                analyze_ok = False
        res.add("POST /api/v1/documents:analyze", analyze_ok, f"status={r.status_code} job_id={analyze_job_id}")

        if analyze_job_id:
            r = await client.get(f"/api/v1/jobs/{analyze_job_id}")
            job_status_ok = r.status_code == 200 and "job_id" in r.json()
            res.add("GET /api/v1/jobs/{job_id}", job_status_ok, f"status={r.status_code}")

            # Note: We do not wait for completion in this smoke test (job runs in background)
            # Simply verify the schema when status is 'running'
            if r.status_code == 200:
                job_data = r.json()
                schema_ok = all(k in job_data for k in ("job_id", "status", "progress", "message"))
                res.add("Phase 1 JobStatus schema", schema_ok, f"fields={list(job_data.keys())}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DocuVision API contract smoke test")
    parser.add_argument("--file", default=None, help="Optional image/PDF path for upload lifecycle checks")
    args = parser.parse_args()

    if args.file:
        test_file = Path(args.file)
        if not test_file.exists():
            print(_fail(f"File not found: {test_file}"))
            sys.exit(1)
    else:
        test_file = _find_default_test_file()

    results = Results()
    asyncio.run(run_contract_checks(test_file, results))
    ok = results.done()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
