"""Lite runtime feature flags."""

from __future__ import annotations

from app.core.config import settings


def raster_table_extraction_enabled() -> bool:
    """Return True when image/scan Table Transformer extraction is allowed."""
    return settings.RASTER_TABLE_EXTRACTION_ENABLED
