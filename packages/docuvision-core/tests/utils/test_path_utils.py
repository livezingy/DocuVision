"""Tests for path resolution helpers."""

from __future__ import annotations

from unittest.mock import patch

from docuvision_core.utils.path_utils import resolve_tesseract_cmd


def test_resolve_tesseract_cmd_prefers_path_binary() -> None:
    with patch("shutil.which", return_value="/usr/bin/tesseract"):
        assert resolve_tesseract_cmd("/missing/tesseract.exe") == "/usr/bin/tesseract"


def test_resolve_tesseract_cmd_uses_configured_file_when_present(tmp_path) -> None:
    fake = tmp_path / "tesseract"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    assert resolve_tesseract_cmd(str(fake)) == str(fake)
