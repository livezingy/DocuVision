# core/extractors/__init__.py
"""
表格提取器模�?

提供统一的表格提取接口，支持多种提取方法（Camelot、PDFPlumber等）
"""

# 延迟导入，优化启动性能
_extractors_loaded = False

def _lazy_register():
    """延迟注册提取器，优化模块加载性能"""
    global _extractors_loaded
    if not _extractors_loaded:
        from docuvision_core.extractors.camelot_extractor import CamelotExtractor
        from docuvision_core.extractors.pdfplumber_extractor import PDFPlumberExtractor
        from docuvision_core.extractors.factory import ExtractorFactory
        
        # 注册提取�?
        ExtractorFactory.register('camelot', CamelotExtractor)
        ExtractorFactory.register('pdfplumber', PDFPlumberExtractor)
        
        _extractors_loaded = True

# 导入基类和工厂（这些是轻量级的）
from docuvision_core.extractors.base import BaseExtractor
from docuvision_core.extractors.factory import ExtractorFactory

# 导入提取器类（用�?__all__ 导出�?
from docuvision_core.extractors.camelot_extractor import CamelotExtractor
from docuvision_core.extractors.pdfplumber_extractor import PDFPlumberExtractor

# 延迟注册提取�?
_lazy_register()

__all__ = ['BaseExtractor', 'ExtractorFactory', 'CamelotExtractor', 'PDFPlumberExtractor']
