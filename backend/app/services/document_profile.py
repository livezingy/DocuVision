"""Document Profile pre-scan for Pro (engine/flavor recommendation)."""

from __future__ import annotations

from typing import Any, Dict

from app.services.document_type_classifier import classify_document
from app.services.file_type_detector import detect_file_type

# Table mapping UI mode (processingMode=table_mapping) routing by detected_file_type:
# - pdf_digital (v1.4): analyze with enable_layout=false, docuvision-core TableProcessor, table_template.
# - pdf_scan / image (future): enable_layout=true, Tables on, mapping quality gate TBD; UI mode id unchanged.


def build_document_profile(file_path: str) -> Dict[str, Any]:
    detected, page_count = detect_file_type(file_path)
    classification = classify_document(file_path)
    flavor = "auto"
    engine = "auto"
    if detected.value == "pdf_digital":
        engine = "docuvision_core"
        flavor = "auto"
    elif detected.value in {"pdf_scan", "image"}:
        engine = "ppstructure"
    return {
        "detected_file_type": detected.value,
        "page_count": page_count,
        "suggested_document_type": classification.get("document_type", "auto"),
        "classification_confidence": classification.get("confidence", 0.0),
        "suggested_routing": {
            "enable_layout": detected.value != "pdf_digital",
            "enable_table": True,
            "table_engine": engine,
            "flavor": flavor,
        },
    }
