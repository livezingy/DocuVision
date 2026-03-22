"""
OCR Recognition Module Configuration
"""

from pydantic import BaseModel


class OCRRecognitionConfig(BaseModel):
    """OCR Recognition模块配置"""
    enabled: bool = True
    engine: str = "paddleocr"  # paddleocr, tesseract, easyocr
    language: str = "ch"  # ch, en, multi
    use_gpu: bool = False
    
    class Config:
        extra = "allow"
