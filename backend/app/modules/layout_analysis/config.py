"""
Layout Analysis Module Configuration
"""

from pydantic import BaseModel
from typing import Optional


class LayoutAnalysisConfig(BaseModel):
    """Layout Analysis模块配置"""
    enabled: bool = True
    engine: str = "ppstructure"  # ppstructure, layoutparser
    use_gpu: bool = False
    recovery: bool = True  # PP-Structure recovery mode
    lang: str = "ch"  # Language for PP-Structure
    
    class Config:
        extra = "allow"
