"""
NLP Analysis Engines
"""

# PaddleOCR-only version: spaCy and HanLP disabled
# from .spacy_engine import SpaCyEngine
from .simple_engine import SimpleNLPEngine

# HanLP is optional
# try:
#     from .hanlp_engine import HanLPEngine
#     __all__ = ["SpaCyEngine", "HanLPEngine", "SimpleNLPEngine"]
# except ImportError:
#     __all__ = ["SpaCyEngine", "SimpleNLPEngine"]

# PaddleOCR-only version: Only Simple engine exported
__all__ = ["SimpleNLPEngine"]
