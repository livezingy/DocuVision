"""Shared default sample file candidates for Cloud manual test scripts."""

from __future__ import annotations

from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent

DEFAULT_TEST_FILE_CANDIDATES: list[Path] = [
    _PROJECT_ROOT / "test_data" / "testfiles" / "images" / "kie" / "id_card_sample_01.jpg",
    _PROJECT_ROOT / "test_data" / "testfiles" / "invoices" / "sample-invoice.png",
    _PROJECT_ROOT / "test_data" / "testfiles" / "images" / "kie",
    _PROJECT_ROOT / "test_data" / "testfiles" / "pdf",
    _PROJECT_ROOT / "test_data" / "testfiles" / "invoices",
]

DEFAULT_TEST_FILE_EXAMPLE = (
    _PROJECT_ROOT / "test_data" / "testfiles" / "invoices" / "sample-invoice.png"
)


def find_default_test_file() -> Path | None:
    for candidate in DEFAULT_TEST_FILE_CANDIDATES:
        if candidate.is_file():
            return candidate
        if candidate.is_dir():
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.pdf"):
                files = sorted(candidate.glob(ext))
                if files:
                    return files[0]
    return None
