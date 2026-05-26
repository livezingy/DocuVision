"""Build LiteResult responses."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.schemas.lite_result import (
    DetectedFileType,
    JobStatus,
    LiteExportLinks,
    LiteHint,
    LiteInputMeta,
    LiteOcrBlock,
    LiteQualityMeta,
    LiteResult,
    LiteRoutingMeta,
    LiteTable,
    LiteTableDetails,
    LiteWarning,
    Severity,
    WarningCode,
)
from app.services.file_detector import detect_file_type

_DEMO_MAPPING_PATH = Path(__file__).resolve().parents[1] / "config" / "demo_classification_mappings.json"


def _enrich_demo_fields(pipeline_output: Dict[str, Any], tables: List[LiteTable]) -> tuple[list, list]:
    from docuvision_core.demo.classification_mapper import apply_classification_mappings, load_mapping_config
    from docuvision_core.demo.transaction_mapper import extract_transactions_from_result

    payload = {
        "tables": [t.model_dump(mode="json") for t in tables],
        "kie_fields": pipeline_output.get("kie_fields") or {},
    }
    transactions = extract_transactions_from_result(payload)
    config = load_mapping_config(_DEMO_MAPPING_PATH)
    mapped = apply_classification_mappings(transactions, config)
    return transactions, mapped


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_lite_result(
    *,
    job_id: Optional[str] = None,
    file_path: Path,
    mime_type: str,
    pipeline_output: Dict[str, Any],
    status: JobStatus = JobStatus.SUCCEEDED,
    processing_ms: int = 0,
    error: Optional[Dict[str, Any]] = None,
) -> LiteResult:
    job_id = job_id or str(uuid4())
    detected, page_count = detect_file_type(file_path, mime_type)
    if pipeline_output.get("detected_file_type"):
        detected = pipeline_output["detected_file_type"]
    if pipeline_output.get("page_count"):
        page_count = pipeline_output["page_count"]

    tables = [
        LiteTable(
            table_id=t["table_id"],
            page=t["page"],
            index_on_page=t["index_on_page"],
            bbox=t.get("bbox", []),
            row_count=t.get("row_count", 0),
            col_count=t.get("col_count", 0),
            score=t.get("score", 0.0),
            source=t.get("source", ""),
            headers=t.get("headers", []),
            rows=t.get("rows", []),
            details=LiteTableDetails(**t.get("details", {})),
        )
        for t in pipeline_output.get("tables", [])
    ]

    ocr_raw = pipeline_output.get("ocr")
    ocr_blocks = None
    if ocr_raw is not None:
        ocr_blocks = [LiteOcrBlock(**b) for b in ocr_raw]

    warnings: List[LiteWarning] = []
    for w in pipeline_output.get("warnings", []):
        code = w.get("code")
        try:
            warning_code = WarningCode(code)
        except ValueError:
            continue
        warnings.append(
            LiteWarning(code=warning_code, message=w.get("message", ""), severity=Severity.WARNING)
        )

    hints: List[LiteHint] = []
    if detected == DetectedFileType.PDF_SCAN:
        hints.append(
            LiteHint(
                code="pro_recommended",
                message="For scan/layout/KIE quality, use DocuVision Pro.",
                link="https://github.com/livezingy/DocuVision",
            )
        )

    routing_data = pipeline_output.get("routing", {})
    quality_data = pipeline_output.get("quality", {})

    transactions, mapped_transactions = _enrich_demo_fields(pipeline_output, tables)

    return LiteResult(
        job_id=job_id,
        status=status,
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        processing_ms=processing_ms,
        input=LiteInputMeta(
            filename=file_path.name,
            file_size_bytes=file_path.stat().st_size,
            mime_type=mime_type,
            detected_file_type=detected,
            page_count=page_count,
            sha256=_sha256(file_path),
        ),
        routing=LiteRoutingMeta(**routing_data),
        quality=LiteQualityMeta(**quality_data),
        tables=tables,
        ocr=ocr_blocks,
        text_preview=pipeline_output.get("text_preview"),
        exports=LiteExportLinks(
            csv=f"/api/v1/lite/export/{job_id}.csv",
            xlsx=f"/api/v1/lite/export/{job_id}.xlsx",
            json=f"/api/v1/lite/jobs/{job_id}/result",
        ),
        warnings=warnings,
        hints=hints,
        transactions=transactions,
        mapped_transactions=mapped_transactions,
        error=error,
    )


def timed_pipeline(fn, *args, **kwargs) -> tuple[Any, int]:
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = int((time.perf_counter() - start) * 1000)
    return result, elapsed
