# core/extractors/pdfplumber_extractor.py
"""
PDFPlumber表格提取�?

封装PDFPlumber的lines和text模式表格提取功能
"""

from typing import Dict, List, Optional, Any
import pdfplumber
from docuvision_core.extractors.base import BaseExtractor
from docuvision_core.processing.table_evaluator import TableEvaluator, PDFPlumberTableWrapper
from docuvision_core.utils.logger import AppLogger


class PDFPlumberExtractor(BaseExtractor):
    """PDFPlumber表格提取�?""
    
    def __init__(self, **kwargs):
        """
        初始化PDFPlumber提取�?
        
        Args:
            **kwargs: 其他参数（预留）
        """
        self.logger = AppLogger.get_logger()
    
    @property
    def name(self) -> str:
        """提取器名�?""
        return "pdfplumber"
    
    @property
    def supported_flavors(self) -> List[str]:
        """支持的flavor列表"""
        return ['lines', 'text']
    
    def calculate_params(self, feature_analyzer, table_type: str, **kwargs) -> Dict:
        """
        计算参数
        
        Args:
            feature_analyzer: PageFeatureAnalyzer实例
            table_type: 'bordered' �?'unbordered'
            **kwargs: 其他参数（预留）
                
        Returns:
            Dict: 参数字典
        """
        from docuvision_core.processing.table_params_calculator import TableParamsCalculator
        
        calculator = TableParamsCalculator(feature_analyzer)
        return calculator.get_pdfplumber_params(table_type)
    
    def extract_tables(self, page, feature_analyzer, params: Dict) -> List[Dict]:
        """
        提取表格
        
        Args:
            page: pdfplumber.Page对象
            feature_analyzer: PageFeatureAnalyzer实例
            params: 参数字典，包含：
                - flavor: 'lines' �?'text'（可选，自动选择�?
                - param_mode: 'default', 'auto', 'custom'
                - custom_params: 自定义参数（当param_mode='custom'时）
                - score_threshold: 评分阈�?
                
        Returns:
            List[Dict]: 表格结果列表
        """
        flavor = params.get('flavor')
        if flavor is None:
            # 根据table_type自动选择
            table_type = feature_analyzer.predict_table_type()
            if table_type == 'bordered':
                flavor = 'lines'
            else:
                flavor = 'text'
        
        if flavor == 'lines':
            return self._extract_lines(page, feature_analyzer, params)
        elif flavor == 'text':
            return self._extract_text(page, feature_analyzer, params)
        else:
            self.logger.error(f"Unsupported flavor: {flavor}")
            return []
    
    def _extract_lines(self, page, feature_analyzer, params: Dict) -> List[Dict]:
        """使用lines模式提取表格"""
        evaluator = TableEvaluator()
        evaluator.source = "pdfplumber"
        evaluator.flavor = "lines"
        
        # 获取参数
        param_mode = params.get('pdfplumber_param_mode', params.get('param_mode', 'auto'))
        if param_mode == 'custom' and 'pdfplumber_custom_params' in params:
            extract_params = params['pdfplumber_custom_params'].copy()
        elif param_mode == 'custom' and 'custom_params' in params:
            extract_params = params['custom_params'].copy()
        elif param_mode == 'default':
            from docuvision_core.utils.param_config import get_default_pdfplumber_params
            extract_params = get_default_pdfplumber_params()
        else:  # auto
            extract_params = self.calculate_params(feature_analyzer, 'bordered')
        
        # 确保strategy设置
        if 'vertical_strategy' not in extract_params:
            extract_params['vertical_strategy'] = 'lines'
        if 'horizontal_strategy' not in extract_params:
            extract_params['horizontal_strategy'] = 'lines'
        
        self.logger.debug(f"[PDFPlumberExtractor] Using lines parameters: {extract_params}")
        
        try:
            tables = page.find_tables(extract_params)
        except Exception as e:
            self.logger.error(f"PDFPlumber lines extraction failed: {str(e)}")
            return []
        
        page_num = getattr(page, 'page_number', '?')
        self.logger.info(f"[PDFPlumberExtractor] Detected {len(tables)} tables on page {page_num}")
        
        # 评估和格式化结果
        results = []
        score_threshold = params.get('score_threshold', 0.0)
        
        for idx, p_table in enumerate(tables):
            wrapper = PDFPlumberTableWrapper(p_table, page)
            p_score, p_details, p_domain = evaluator.evaluate(wrapper)
            
            if p_score >= score_threshold:
                results.append({
                    'table': wrapper,
                    'bbox': p_table.bbox,
                    'score': p_score,
                    'details': p_details,
                    'domain': p_domain,
                    'source': 'pdfplumber_lines'
                })
                self.logger.info(
                    f"[PDFPlumberExtractor] Lines table {idx+1}: "
                    f"score={p_score:.3f}, domain={p_domain}, "
                    f"bbox={p_table.bbox}"
                )
        
        return results
    
    def _extract_text(self, page, feature_analyzer, params: Dict) -> List[Dict]:
        """使用text模式提取表格"""
        evaluator = TableEvaluator()
        evaluator.source = "pdfplumber"
        evaluator.flavor = "text"
        
        # 获取参数
        param_mode = params.get('pdfplumber_param_mode', params.get('param_mode', 'auto'))
        if param_mode == 'custom' and 'pdfplumber_custom_params' in params:
            extract_params = params['pdfplumber_custom_params'].copy()
        elif param_mode == 'custom' and 'custom_params' in params:
            extract_params = params['custom_params'].copy()
        elif param_mode == 'default':
            from docuvision_core.utils.param_config import get_default_pdfplumber_params
            extract_params = get_default_pdfplumber_params()
        else:  # auto
            extract_params = self.calculate_params(feature_analyzer, 'unbordered')
        
        # 确保strategy设置
        if 'vertical_strategy' not in extract_params:
            extract_params['vertical_strategy'] = 'text'
        if 'horizontal_strategy' not in extract_params:
            extract_params['horizontal_strategy'] = 'text'
        
        self.logger.debug(f"[PDFPlumberExtractor] Using text parameters: {extract_params}")
        
        try:
            tables = page.find_tables(extract_params)
        except Exception as e:
            self.logger.error(f"PDFPlumber text extraction failed: {str(e)}")
            return []
        
        page_num = getattr(page, 'page_number', '?')
        self.logger.info(f"[PDFPlumberExtractor] Detected {len(tables)} tables on page {page_num}")
        
        # 评估和格式化结果
        results = []
        score_threshold = params.get('score_threshold', 0.0)
        
        for idx, p_table in enumerate(tables):
            wrapper = PDFPlumberTableWrapper(p_table, page)
            p_score, p_details, p_domain = evaluator.evaluate(wrapper)
            
            if p_score >= score_threshold:
                results.append({
                    'table': wrapper,
                    'bbox': p_table.bbox,
                    'score': p_score,
                    'details': p_details,
                    'domain': p_domain,
                    'source': 'pdfplumber_text'
                })
                self.logger.info(
                    f"[PDFPlumberExtractor] Text table {idx+1}: "
                    f"score={p_score:.3f}, domain={p_domain}, "
                    f"bbox={p_table.bbox}"
                )
        
        return results
