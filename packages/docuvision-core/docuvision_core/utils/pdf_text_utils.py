"""Utilities for cleaning text extracted from PDF engines."""

from __future__ import annotations

import re
from typing import Any

_CID_TOKEN = re.compile(r"\(cid:(\d+)\)")
_CID_RUN = re.compile(r"(?:\(cid:\d+\))+")


def decode_cid_placeholders(text: str) -> str:
    """Decode pdfminer/pdfplumber (cid:N) runs into Unicode when possible."""
    if not text or "(cid:" not in text:
        return text

    def _decode_run(match: re.Match[str]) -> str:
        codes = [int(m.group(1)) for m in _CID_TOKEN.finditer(match.group(0))]
        if not codes:
            return match.group(0)
        if all(code <= 255 for code in codes):
            try:
                return bytes(codes).decode("utf-8")
            except UnicodeDecodeError:
                pass
        if len(codes) == 1 and codes[0] < 0x110000:
            try:
                return chr(codes[0])
            except ValueError:
                pass
        return ""

    text = _CID_RUN.sub(_decode_run, text)
    return _CID_TOKEN.sub("", text)


def sanitize_pdf_text(value: Any) -> str:
    """Normalize a single extracted PDF text value for display/export."""
    if value is None:
        return ""
    text = str(value)
    text = decode_cid_placeholders(text)
    return " ".join(text.split())


def normalize_pdf_text_preserve_paragraphs(value: Any) -> str:
    """Keep paragraph breaks from pdfplumber extract_text while normalizing lines."""
    if value is None:
        return ""
    text = decode_cid_placeholders(str(value))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [" ".join(line.split()) for line in block.split("\n") if line.strip()]
        if lines:
            paragraphs.append("\n".join(lines))
    return "\n\n".join(paragraphs)
