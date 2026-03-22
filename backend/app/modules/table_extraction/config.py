"""
Table Extraction Module Configuration
"""

from pydantic import BaseModel


class TableExtractionConfig(BaseModel):
    """Table Extraction模块配置"""
    enabled: bool = True
    engine: str = "ppstructure"  # ppstructure, camelot, tabula
    use_gpu: bool = False
    
    class Config:
        extra = "allow"
