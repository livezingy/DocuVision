"""Generate per-sample KIE hit/miss report (JSON + Markdown).

This script calls Phase 1 API endpoints and writes a persistent report for
invoice samples defined in tracker item 1.

Usage:
    cd backend
    python tests/generate_kie_hit_miss_report.py

Optional environment variables:
    BASE_URL=http://127.0.0.1:8000
    KIE_REPORT_TIMEOUT_SECONDS=300
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError as exc:
    raise SystemExit("httpx is required: pip install httpx") from exc


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
REPORT_DIR = SCRIPT_DIR / "reports"
REPORT_JSON = REPORT_DIR / "kie_hit_miss_report.json"
REPORT_MD = REPORT_DIR / "kie_hit_miss_report.md"

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
POLL_TIMEOUT_SECONDS = int(os.getenv("KIE_REPORT_TIMEOUT_SECONDS", "300"))

SAMPLE_MATRIX = [
    PROJECT_ROOT / "test_data" / "templates" / "invoice" / "invoice_sample_01.pdf",
    PROJECT_ROOT / "test_data" / "templates" / "invoice" / "receipt-invoice-like.png",
    PROJECT_ROOT / "test_data" / "templates" / "invoice" / "sample-invoice.png",
]


@dataclass
class SampleResult:
    sample_path: str
    file_exists: bool
    submit_status_code: int | None
    job_id: str
    final_status: str
    kie_stage: str
    kie_fields_count: int | None
    accepted: bool
    hit_miss: str
    note: str


def evaluate_acceptance(kie_stage: str, kie_fields_count: int) -> tuple[bool, str]:
    """Rule KIE-ACCEPT-001: completed + non-negative count is accepted."""
    if kie_stage != "completed":
        return False, f"stage_not_completed:{kie_stage}"
    if kie_fields_count < 0:
        return False, f"invalid_negative_count:{kie_fields_count}"
    if kie_fields_count == 0:
        return True, "completed_with_zero_fields_allowed"
    return True, "completed_with_field_hits"


async def analyze_one_sample(client: httpx.AsyncClient, sample: Path) -> SampleResult:
    sample_path = str(sample.relative_to(PROJECT_ROOT)).replace("\\", "/")
    if not sample.exists():
        return SampleResult(
            sample_path=sample_path,
            file_exists=False,
            submit_status_code=None,
            job_id="",
            final_status="missing_sample",
            kie_stage="",
            kie_fields_count=None,
            accepted=False,
            hit_miss="error",
            note="sample file not found",
        )

    ext = sample.suffix.lower().lstrip(".")
    mime = "application/pdf" if ext == "pdf" else f"image/{ext}"

    try:
        with open(sample, "rb") as fh:
            submit = await client.post(
                "/api/v1/documents:analyze",
                files={"file": (sample.name, fh, mime)},
                data={
                    "enable_kie": "true",
                    "document_type": "invoice",
                    "return_raw": "false",
                },
            )
    except Exception as exc:
        return SampleResult(
            sample_path=sample_path,
            file_exists=True,
            submit_status_code=None,
            job_id="",
            final_status="submit_error",
            kie_stage="",
            kie_fields_count=None,
            accepted=False,
            hit_miss="error",
            note=f"submit exception: {exc}",
        )

    if submit.status_code != 200:
        return SampleResult(
            sample_path=sample_path,
            file_exists=True,
            submit_status_code=submit.status_code,
            job_id="",
            final_status="submit_failed",
            kie_stage="",
            kie_fields_count=None,
            accepted=False,
            hit_miss="error",
            note=f"submit failed: {submit.text[:200]}",
        )

    job_id = str(submit.json().get("job_id", ""))
    if not job_id:
        return SampleResult(
            sample_path=sample_path,
            file_exists=True,
            submit_status_code=submit.status_code,
            job_id="",
            final_status="submit_failed",
            kie_stage="",
            kie_fields_count=None,
            accepted=False,
            hit_miss="error",
            note="missing job_id in submit response",
        )

    deadline = time.time() + POLL_TIMEOUT_SECONDS
    final_status = "running"

    while time.time() < deadline:
        try:
            status_resp = await client.get(f"/api/v1/jobs/{job_id}")
        except Exception as exc:
            return SampleResult(
                sample_path=sample_path,
                file_exists=True,
                submit_status_code=submit.status_code,
                job_id=job_id,
                final_status="status_error",
                kie_stage="",
                kie_fields_count=None,
                accepted=False,
                hit_miss="error",
                note=f"status exception: {exc}",
            )

        if status_resp.status_code != 200:
            return SampleResult(
                sample_path=sample_path,
                file_exists=True,
                submit_status_code=submit.status_code,
                job_id=job_id,
                final_status="status_failed",
                kie_stage="",
                kie_fields_count=None,
                accepted=False,
                hit_miss="error",
                note=f"status failed: {status_resp.text[:200]}",
            )

        final_status = str(status_resp.json().get("status", "unknown"))
        if final_status in {"succeeded", "completed", "failed", "cancelled"}:
            break

        await asyncio.sleep(1)

    if final_status not in {"succeeded", "completed"}:
        return SampleResult(
            sample_path=sample_path,
            file_exists=True,
            submit_status_code=submit.status_code,
            job_id=job_id,
            final_status=final_status,
            kie_stage="",
            kie_fields_count=None,
            accepted=False,
            hit_miss="error",
            note=f"job did not complete successfully: {final_status}",
        )

    try:
        result_resp = await client.get(f"/api/v1/jobs/{job_id}/result")
    except Exception as exc:
        return SampleResult(
            sample_path=sample_path,
            file_exists=True,
            submit_status_code=submit.status_code,
            job_id=job_id,
            final_status=final_status,
            kie_stage="",
            kie_fields_count=None,
            accepted=False,
            hit_miss="error",
            note=f"result exception: {exc}",
        )

    if result_resp.status_code != 200:
        return SampleResult(
            sample_path=sample_path,
            file_exists=True,
            submit_status_code=submit.status_code,
            job_id=job_id,
            final_status=final_status,
            kie_stage="",
            kie_fields_count=None,
            accepted=False,
            hit_miss="error",
            note=f"result failed: {result_resp.text[:200]}",
        )

    body: dict[str, Any] = result_resp.json() if isinstance(result_resp.json(), dict) else {}
    quality = body.get("quality", {}) if isinstance(body.get("quality"), dict) else {}
    kie_stage = str(quality.get("kie_stage", ""))

    try:
        kie_fields_count = int(quality.get("kie_fields_count", 0) or 0)
    except Exception:
        kie_fields_count = -1

    accepted, note = evaluate_acceptance(kie_stage, kie_fields_count)
    if accepted and kie_fields_count > 0:
        hit_miss = "hit"
    elif accepted:
        hit_miss = "miss"
    else:
        hit_miss = "error"

    return SampleResult(
        sample_path=sample_path,
        file_exists=True,
        submit_status_code=submit.status_code,
        job_id=job_id,
        final_status=final_status,
        kie_stage=kie_stage,
        kie_fields_count=kie_fields_count,
        accepted=accepted,
        hit_miss=hit_miss,
        note=note,
    )


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# KIE Hit/Miss Report")
    lines.append("")
    lines.append(f"Generated at: {report['generated_at_utc']}")
    lines.append(f"Base URL: {report['base_url']}")
    lines.append(f"Rule: {report['rule_id']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- total: {report['summary']['total']}")
    lines.append(f"- accepted: {report['summary']['accepted']}")
    lines.append(f"- hit: {report['summary']['hit']}")
    lines.append(f"- miss: {report['summary']['miss']}")
    lines.append(f"- error: {report['summary']['error']}")
    lines.append("")
    lines.append("## Per-sample")
    lines.append("")
    lines.append("| sample_path | final_status | kie_stage | kie_fields_count | accepted | hit_miss | note |")
    lines.append("|---|---|---|---:|---|---|---|")

    for row in report["samples"]:
        count = "" if row["kie_fields_count"] is None else str(row["kie_fields_count"])
        safe_note = str(row["note"]).replace("|", "/")
        lines.append(
            f"| {row['sample_path']} | {row['final_status']} | {row['kie_stage']} | {count} | "
            f"{row['accepted']} | {row['hit_miss']} | {safe_note} |"
        )

    lines.append("")
    return "\n".join(lines)


async def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=180) as client:
        results = []
        for sample in SAMPLE_MATRIX:
            results.append(await analyze_one_sample(client, sample))

    rows = [asdict(r) for r in results]
    summary = {
        "total": len(rows),
        "accepted": sum(1 for r in rows if r["accepted"]),
        "hit": sum(1 for r in rows if r["hit_miss"] == "hit"),
        "miss": sum(1 for r in rows if r["hit_miss"] == "miss"),
        "error": sum(1 for r in rows if r["hit_miss"] == "error"),
    }

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "rule_id": "KIE-ACCEPT-001",
        "samples": rows,
        "summary": summary,
    }

    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_markdown(report), encoding="utf-8")

    print(f"[KIE-REPORT] JSON: {REPORT_JSON}")
    print(f"[KIE-REPORT] MD:   {REPORT_MD}")
    print(f"[KIE-REPORT] Summary: {summary}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
