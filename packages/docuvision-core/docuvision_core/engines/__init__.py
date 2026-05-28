# core/engines/__init__.py
"""OCR and table detection engine package."""

_engines_loaded = False


def _lazy_register() -> None:
    """Register built-in engines on first use; skip optional deps when missing."""
    global _engines_loaded
    if _engines_loaded:
        return

    from docuvision_core.engines.easyocr_engine import EasyOCREngine
    from docuvision_core.engines.factory import EngineFactory

    EngineFactory.register_ocr("easyocr", EasyOCREngine)

    try:
        from docuvision_core.engines.transformer_engine import TransformerEngine

        EngineFactory.register_detection("transformer", TransformerEngine)
    except ImportError:
        pass

    try:
        from docuvision_core.engines.paddleocr_engine import PaddleOCREngine

        EngineFactory.register_ocr("paddleocr", PaddleOCREngine)
        EngineFactory.register_detection("paddleocr", PaddleOCREngine)
    except ImportError:
        pass

    _engines_loaded = True


from docuvision_core.engines.base import BaseOCREngine, BaseDetectionEngine
from docuvision_core.engines.factory import EngineFactory

__all__ = [
    "BaseOCREngine",
    "BaseDetectionEngine",
    "EngineFactory",
    "_lazy_register",
]
