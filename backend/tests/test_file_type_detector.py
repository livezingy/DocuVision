"""Tests for Pro file type detector."""

from app.services.file_type_detector import DetectedFileType, detect_file_type


def test_detect_image() -> None:
    detected, pages = detect_file_type("sample.png")
    assert detected == DetectedFileType.IMAGE
    assert pages == 1
