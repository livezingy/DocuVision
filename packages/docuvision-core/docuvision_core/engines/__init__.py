# core/engines/__init__.py
"""OCR and table detection engine package."""

# Lazy registration to improve import time
_engines_loaded = False


def _lazy_register():
    """Register built-in engines on first use."""
    global _engines_loaded
    if not _engines_loaded:
        from docuvision_core.engines.easyocr_engine import EasyOCREngine
        from docuvision_core.engines.transformer_engine import TransformerEngine
        from docuvision_core.engines.paddleocr_engine import PaddleOCREngine
        from docuvision_core.engines.factory import EngineFactory

        EngineFactory.register_ocr('easyocr', EasyOCREngine)
        EngineFactory.register_detection('transformer', TransformerEngine)
        EngineFactory.register_ocr('paddleocr', PaddleOCREngine)
        EngineFactory.register_detection('paddleocr', PaddleOCREngine)

        _engines_loaded = True


from docuvision_core.engines.base import BaseOCREngine, BaseDetectionEngine
from docuvision_core.engines.factory import EngineFactory
from docuvision_core.engines.easyocr_engine import EasyOCREngine
from docuvision_core.engines.transformer_engine import TransformerEngine
from docuvision_core.engines.paddleocr_engine import PaddleOCREngine

_lazy_register()

__all__ = [
    'BaseOCREngine',
    'BaseDetectionEngine',
    'EngineFactory',
    'EasyOCREngine',
    'TransformerEngine',
    'PaddleOCREngine',
]
