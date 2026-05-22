# core/extractors/camelot_extractor.py
"""
Camelot表格提取噀

封装Camelot的lattice和stream模式表格提取功能
"""

import os
import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from docuvision_core.extractors.base import BaseExtractor
from docuvision_core.processing.table_evaluator import TableEvaluator
from docuvision_core.utils.logger import AppLogger


class CamelotExtractor(BaseExtractor):
    """Camelot表格提取噀"""
    
    def __init__(self, **kwargs):
        """
        初始化Camelot提取噀
        
        Args:
            **kwargs: 其他参数（预留）
        """
        self.logger = AppLogger.get_logger()
        # 延迟导入camelot，避免在模块导入时因系统依赖问题导致应用启动失败
        # 不在初始化时立即导入，而是在首次使用时导入（懒加载！
        self._camelot = None
        self._camelot_import_attempted = False
    
    def _ensure_camelot_imported(self):
        """确保camelot已导入（懒加载优化）"""
        if self._camelot is not None:
            return True
        
        if self._camelot_import_attempted:
            return False  # 已经尝试过但失败了
        
        # 在导入camelot之前设置环境变量，避免在无头环境中加载OpenGL庀
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ.setdefault('DISPLAY', '')
        os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '0')
        # 设置MESA GL版本，避免OpenGL相关错误
        os.environ.setdefault('MESA_GL_VERSION_OVERRIDE', '3.3')
        
        self._camelot_import_attempted = True
        
        try:
            import camelot
            self._camelot = camelot
            return True
        except ImportError as e:
            self.logger.error(f"Failed to import camelot: {e}")
            self._camelot = None
            return False
        except Exception as e:
            # 捕获libGL.so.1等OpenGL相关错误，但这些错误通常不影响camelot的基本功能
            error_str = str(e).lower()
            if 'libgl' in error_str or 'opengl' in error_str:
                # libGL错误通常是警告性的，camelot在headless模式下仍可使生
                self.logger.warning(f"Camelot import warning (libGL/OpenGL): {e}. Camelot may still work in headless mode.")
                try:
                    # 尝试再次导入，有时第二次会成劀
                    import camelot
                    self._camelot = camelot
                    return True
                except:
                    # 即使有libGL错误，也认为camelot可用（因为可能只是警告）
                    self.logger.warning("Camelot may have OpenGL warnings but should still be usable.")
                    import camelot
                    self._camelot = camelot
                    return True
            else:
                self.logger.error(f"Unexpected error importing camelot: {e}")
                self._camelot = None
                return False
    
    @property
    def name(self) -> str:
        """提取器名秀"""
        return "camelot"
    
    @property
    def supported_flavors(self) -> List[str]:
        """支持的flavor列表"""
        return ['lattice', 'stream']
    
    def calculate_params(self, feature_analyzer, table_type: str, **kwargs) -> Dict:
        """
        计算参数
        
        Args:
            feature_analyzer: PageFeatureAnalyzer实例
            table_type: 'bordered' 成'unbordered'
            **kwargs: 其他参数
                - image_shape: 图像尺寸 (height, width)，用于lattice模式
                - flavor: 指定flavor！lattice'成stream'），如果不指定则根据table_type自动选择
                
        Returns:
            Dict: 参数字典
        """
        flavor = kwargs.get('flavor')
        if flavor is None:
            # 根据table_type自动选择flavor
            flavor = 'lattice' if table_type == 'bordered' else 'stream'
        
        if flavor == 'lattice':
            return self._calculate_lattice_params(feature_analyzer, **kwargs)
        elif flavor == 'stream':
            return self._calculate_stream_params(feature_analyzer)
        else:
            raise ValueError(f"Unsupported flavor: {flavor}")
    
    def _calculate_lattice_params(self, feature_analyzer, **kwargs) -> Dict:
        """计算lattice模式参数"""
        from docuvision_core.processing.table_params_calculator import TableParamsCalculator
        
        calculator = TableParamsCalculator(feature_analyzer)
        image_shape = kwargs.get('image_shape')
        return calculator.get_camelot_lattice_params(image_shape)
    
    def _calculate_stream_params(self, feature_analyzer) -> Dict:
        """计算stream模式参数"""
        from docuvision_core.processing.table_params_calculator import TableParamsCalculator
        
        calculator = TableParamsCalculator(feature_analyzer)
        return calculator.get_camelot_stream_params()
    
    def extract_tables(self, page, feature_analyzer, params: Dict) -> List[Dict]:
        """
        提取表格
        
        Args:
            page: pdfplumber.Page对象
            feature_analyzer: PageFeatureAnalyzer实例
            params: 参数字典，包含：
                - pdf_path: PDF文件路径（必需！
                - page_num: 页码（必需！
                - flavor: 'lattice' 成'stream'（可选，自动选择！
                - param_mode: 'default', 'auto', 'custom'
                - custom_params: 自定义参数（当param_mode='custom'时）
                - score_threshold: 评分阈倀
                - table_areas: 表格区域列表（可选）
                
        Returns:
            List[Dict]: 表格结果列表
        """
        # 懒加载camelot
        if not self._ensure_camelot_imported():
            self.logger.error("Camelot is not available")
            return []
        
        # 获取必需参数
        pdf_path = params.get('pdf_path')
        page_num = params.get('page_num')
        
        if pdf_path is None or page_num is None:
            self.logger.error("pdf_path and page_num are required for Camelot extraction")
            return []
        
        flavor = params.get('flavor')
        if flavor is None:
            # 根据table_type自动选择
            table_type = feature_analyzer.predict_table_type()
            flavor = 'lattice' if table_type == 'bordered' else 'stream'
        
        if flavor == 'lattice':
            return self._extract_lattice(pdf_path, page_num, page, feature_analyzer, params)
        elif flavor == 'stream':
            return self._extract_stream(pdf_path, page_num, page, feature_analyzer, params)
        else:
            self.logger.error(f"Unsupported flavor: {flavor}")
            return []
    
    def _extract_lattice(self, pdf_path: str, page_num: int, page, feature_analyzer, params: Dict) -> List[Dict]:
        """使用lattice模式提取表格"""
        evaluator = TableEvaluator()
        evaluator.source = "camelot"
        evaluator.flavor = "lattice"
        
        # 获取参数
        param_mode = params.get('camelot_lattice_param_mode', params.get('param_mode', 'auto'))
        if param_mode == 'custom' and 'camelot_lattice_custom_params' in params:
            extract_params = params['camelot_lattice_custom_params'].copy()
        elif param_mode == 'custom' and 'custom_params' in params:
            extract_params = params['custom_params'].copy()
        elif param_mode == 'default':
            from docuvision_core.utils.param_config import get_default_camelot_lattice_params
            extract_params = get_default_camelot_lattice_params()
        else:  # auto
            image_shape = (int(page.height * 2), int(page.width * 2))
            extract_params = self._calculate_lattice_params(feature_analyzer, image_shape=image_shape)
        
        # 确保flavor设置
        extract_params['flavor'] = 'lattice'
        extract_params['pages'] = str(page_num)
        
        # 处理table_areas
        if params.get('table_areas'):
            extract_params['table_areas'] = [
                ",".join(map(str, area)) for area in params['table_areas']
            ]
        
        self.logger.info(f"[CamelotExtractor] Using lattice parameters: {extract_params}")
        
        try:
            camelot_tables = self._camelot.read_pdf(pdf_path, **extract_params)
        except Exception as e:
            self.logger.error(f"Camelot lattice extraction failed: {str(e)}")
            return []
        
        self.logger.info(f"[CamelotExtractor] Detected {len(camelot_tables)} tables on page {page_num}")
        
        # 评估和格式化结果
        results = []
        score_threshold = params.get('score_threshold', 0.0)
        
        for idx, ct in enumerate(camelot_tables):
            en_ct = evaluator.enhance_camelot_features(ct)
            c_score, c_details, c_domain = evaluator.evaluate(en_ct)
            
            if c_score >= score_threshold:
                results.append({
                    'table': en_ct,
                    'bbox': getattr(en_ct, 'bbox', None),
                    'score': c_score,
                    'details': c_details,
                    'domain': c_domain,
                    'source': 'camelot_lattice'
                })
                self.logger.info(
                    f"[CamelotExtractor] Lattice table {idx+1}: "
                    f"score={c_score:.3f}, domain={c_domain}, "
                    f"bbox={getattr(en_ct, 'bbox', None)}"
                )
        
        return results
    
    def _extract_stream(self, pdf_path: str, page_num: int, page, feature_analyzer, params: Dict) -> List[Dict]:
        """使用stream模式提取表格"""
        evaluator = TableEvaluator()
        evaluator.source = "camelot"
        evaluator.flavor = "stream"
        
        # 获取参数
        param_mode = params.get('camelot_stream_param_mode', params.get('param_mode', 'auto'))
        if param_mode == 'custom' and 'camelot_stream_custom_params' in params:
            extract_params = params['camelot_stream_custom_params'].copy()
        elif param_mode == 'custom' and 'custom_params' in params:
            extract_params = params['custom_params'].copy()
        elif param_mode == 'default':
            from docuvision_core.utils.param_config import get_default_camelot_stream_params
            extract_params = get_default_camelot_stream_params()
        else:  # auto
            extract_params = self._calculate_stream_params(feature_analyzer)
        
        # 确保flavor设置
        extract_params['flavor'] = 'stream'
        extract_params['pages'] = str(page_num)
        
        # 处理table_areas
        if params.get('table_areas'):
            extract_params['table_areas'] = [
                ",".join(map(str, area)) for area in params['table_areas']
            ]
        
        self.logger.debug(f"[CamelotExtractor] Using stream parameters: {extract_params}")
        
        try:
            camelot_tables = self._camelot.read_pdf(pdf_path, **extract_params)
        except Exception as e:
            self.logger.error(f"Camelot stream extraction failed: {str(e)}")
            return []
        
        self.logger.info(f"[CamelotExtractor] Detected {len(camelot_tables)} tables on page {page_num}")
        
        # 评估和格式化结果
        results = []
        score_threshold = params.get('score_threshold', 0.0)
        
        for idx, ct in enumerate(camelot_tables):
            en_ct = evaluator.enhance_camelot_features(ct)
            c_score, c_details, c_domain = evaluator.evaluate(en_ct)
            
            if c_score >= score_threshold:
                results.append({
                    'table': en_ct,
                    'bbox': getattr(en_ct, 'bbox', None),
                    'score': c_score,
                    'details': c_details,
                    'domain': c_domain,
                    'source': 'camelot_stream'
                })
                self.logger.info(
                    f"[CamelotExtractor] Stream table {idx+1}: "
                    f"score={c_score:.3f}, domain={c_domain}, "
                    f"bbox={getattr(en_ct, 'bbox', None)}"
                )
        
        return results
