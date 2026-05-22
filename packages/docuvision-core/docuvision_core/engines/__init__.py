# core/engines/__init__.py
"""
OCR/检测引擎模块

提供统一的OCR和表格检测接口，支持多种引擎（EasyOCR、Transformer等）
"""

# 延迟导入，优化启动性能
_engines_loaded = False

def _lazy_register():
    """延迟注册引擎，优化模块加载性能"""
    global _engines_loaded
    if not _engines_loaded:
        from docuvision_core.engines.easyocr_engine import EasyOCREngine
        from docuvision_core.engines.transformer_engine import TransformerEngine
        from docuvision_core.engines.paddleocr_engine import PaddleOCREngine
        from docuvision_core.engines.factory import EngineFactory
        
        # 注册引擎
        EngineFactory.register_ocr('easyocr', EasyOCREngine)
        EngineFactory.register_detection('transformer', TransformerEngine)
        # PaddleOCR同时提供OCR和检测功能
        EngineFactory.register_ocr('paddleocr', PaddleOCREngine)
        EngineFactory.register_detection('paddleocr', PaddleOCREngine)
        
        _engines_loaded = True

# 导入基类和工厂（这些是轻量级的）
from docuvision_core.engines.base import BaseOCREngine, BaseDetectionEngine
from docuvision_core.engines.factory import EngineFactory

# 导入引擎类（用于 __all__ 导出）
from docuvision_core.engines.easyocr_engine import EasyOCREngine
from docuvision_core.engines.transformer_engine import TransformerEngine
from docuvision_core.engines.paddleocr_engine import PaddleOCREngine

# 延迟注册引擎
_lazy_register()

__all__ = ['BaseOCREngine', 'BaseDetectionEngine', 'EngineFactory', 'EasyOCREngine', 'TransformerEngine', 'PaddleOCREngine']