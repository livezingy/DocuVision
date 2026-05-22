# core/extractors/__init__.py
"""Table extractor package (Camelot, PDFPlumber)."""

# Lazy registration to improve import time
_extractors_loaded = False


def _lazy_register():
    """Register built-in extractors on first use."""
    global _extractors_loaded
    if not _extractors_loaded:
        from docuvision_core.extractors.camelot_extractor import CamelotExtractor
        from docuvision_core.extractors.pdfplumber_extractor import PDFPlumberExtractor
        from docuvision_core.extractors.factory import ExtractorFactory

        ExtractorFactory.register('camelot', CamelotExtractor)
        ExtractorFactory.register('pdfplumber', PDFPlumberExtractor)

        _extractors_loaded = True


from docuvision_core.extractors.base import BaseExtractor
from docuvision_core.extractors.factory import ExtractorFactory
from docuvision_core.extractors.camelot_extractor import CamelotExtractor
from docuvision_core.extractors.pdfplumber_extractor import PDFPlumberExtractor

_lazy_register()

__all__ = ['BaseExtractor', 'ExtractorFactory', 'CamelotExtractor', 'PDFPlumberExtractor']
