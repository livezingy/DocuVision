"""
OCR Recognition Engines
"""

from .paddleocr_engine import PaddleOCREngine
# PaddleOCR-only version: Tesseract and EasyOCR disabled
# from .tesseract_engine import TesseractOCREngine
# from .easyocr_engine import EasyOCREngine

__all__ = ["PaddleOCREngine"]  # PaddleOCR-only version: Only PaddleOCR exported
# __all__ = ["PaddleOCREngine", "TesseractOCREngine", "EasyOCREngine"]
