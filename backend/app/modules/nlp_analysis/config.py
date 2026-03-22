"""
NLP Analysis Module Configuration
"""

from pydantic import BaseModel


class NLPAnalysisConfig(BaseModel):
    """NLP Analysis模块配置"""
    enabled: bool = True
    engine: str = "spacy"  # spacy, hanlp, simple
    language: str = "en"  # en, zh, ch
    
    class Config:
        extra = "allow"
