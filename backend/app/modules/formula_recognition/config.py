"""
Formula Recognition Module Configuration
"""

from pydantic import BaseModel


class FormulaRecognitionConfig(BaseModel):
    """Formula Recognition模块配置"""
    enabled: bool = True
    engine: str = "ppstructure"  # ppstructure, latexocr
    use_gpu: bool = False
    
    class Config:
        extra = "allow"
