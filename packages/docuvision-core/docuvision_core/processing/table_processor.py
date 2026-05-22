# core/processing/table_processor.py
"""
架构�?
- 使用新的模块化设计：
  * page_feature_analyzer.py - 特征分析
  * table_type_classifier.py - 类型判断
  * table_params_calculator.py - 参数计算
- PageFeatureAnalyzer作为适配器保持向后兼�?
- TableProcessor负责流程编排

"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from PIL import Image
import time
import numpy as np
import pandas as pd
import pdfplumber
# 延迟导入camelot，避免在Streamlit Cloud等环境中导入时因系统依赖问题导致应用启动失败
# camelot只在extract_camelot_*方法中使用时才导�?

from docuvision_core.utils.logger import AppLogger
# 延迟导入TableModels，避免在Streamlit中触发torch相关的asyncio事件循环问题
# TableModels只在需要Transformer功能时才导入，Streamlit中通常不需�?
# 延迟导入：在函数内部按需导入
from docuvision_core.processing.table_evaluator import TableEvaluator, PDFPlumberTableWrapper

# 导入新的模块化组�?
from docuvision_core.processing.page_feature_analyzer import PageFeatureAnalyzer as FeatureAnalyzer
from docuvision_core.processing.table_type_classifier import TableTypeClassifier
from docuvision_core.processing.table_params_calculator import TableParamsCalculator

# 导入提取器工�?
from docuvision_core.extractors.factory import ExtractorFactory


class PageFeatureAnalyzer:
    """
    页面特征分析�?- 适配器类（向后兼容）
    
    这个类作为适配器，内部使用新的模块化组件：
    - FeatureAnalyzer: 特征提取
    - TableTypeClassifier: 类型判断
    - TableParamsCalculator: 参数计算
    
    保持旧API不变，使现有代码无需修改即可继续工作
    """
    
    def __init__(self, page, enable_logging=True):
        """
        初始化适配�?
        
        Args:
            page: pdfplumber.Page对象
            enable_logging: 是否输出详细的页面元素调试信息（默认True�?
        """
        self.page = page
        self.logger = AppLogger.get_logger()
        
        # 初始化新的模块化组件（传递enable_logging参数�?
        self._feature_analyzer = FeatureAnalyzer(page, enable_logging=enable_logging)
        self._classifier = TableTypeClassifier(self._feature_analyzer, page)
        self._calculator = TableParamsCalculator(self._feature_analyzer)
    
    # ===== 代理属性访�?=====
    
    @property
    def char_analysis(self) -> dict:
        """代理到FeatureAnalyzer的char_analysis"""
        return self._feature_analyzer.char_analysis
    
    @property
    def line_analysis(self) -> dict:
        """代理到FeatureAnalyzer的line_analysis"""
        return self._feature_analyzer.line_analysis
    
    @property
    def text_line_analysis(self) -> dict:
        """代理到FeatureAnalyzer的text_line_analysis"""
        return self._feature_analyzer.text_line_analysis
    
    @property
    def word_analysis(self) -> dict:
        """代理到FeatureAnalyzer的word_analysis"""
        return self._feature_analyzer.word_analysis
    
    # ===== 代理方法调用 =====
    
    def predict_table_type(self) -> str:
        """
        代理到TableTypeClassifier的predict_table_type
        
        Returns:
            'bordered' �?'unbordered'
        """
        return self._classifier.predict_table_type()
    
    def get_pdfplumber_params(self, table_type: str = 'bordered') -> dict:
        """
        代理到TableParamsCalculator的get_pdfplumber_params
        
        Args:
            table_type: 'bordered' �?'unbordered'
            
        Returns:
            pdfplumber参数字典
        """
        return self._calculator.get_pdfplumber_params(table_type)
    
    def get_camelot_lattice_params(self, image_shape=None) -> dict:
        """
        代理到TableParamsCalculator的get_camelot_lattice_params
        
        Args:
            image_shape: 图像尺寸，可�?
            
        Returns:
            Camelot lattice参数字典
        """
        return self._calculator.get_camelot_lattice_params(image_shape)
    
    def get_camelot_stream_params(self) -> dict:
        """
        代理到TableParamsCalculator的get_camelot_stream_params
        
        Returns:
            Camelot stream参数字典
        """
        return self._calculator.get_camelot_stream_params()


class TableProcessor:
    """
    表格处理器（流程编排�?
    
    职责�?
    - 编排整体处理流程
    - 调用特征分析器、分类器、参数计算器
    - 执行实际的表格提取（pdfplumber/Camelot�?
    - 结果评分和筛�?
    """
    
    def __init__(self, params: Optional[Dict] = None):
        self.logger = AppLogger.get_logger()
        self.params = params or {}
        self.models = self.params.get('models')


    def process_pdf_page(self, pdf_path, page):
        """
        处理PDF页面（主入口�?
        
        Args:
            pdf_path: PDF文件路径
            page: pdfplumber Page对象
            
        Returns:
            提取的表格列表，包含评分和元数据
        """
        # #region agent log
        from docuvision_core.utils.debug_utils import write_debug_log
        write_debug_log(
            location="table_processor.py:147",
            message="process_pdf_page entry",
            data={
                "pdf_path": str(pdf_path) if pdf_path else None,
                "page_number": getattr(page, "page_number", None) if page else None
            },
            hypothesis_id="E"
        )
        # #endregion
        
        try:
            # 参数有效性检�?
            if not page:
                self.logger.error("Page object is None")
                return []
            
            if not pdf_path or not isinstance(pdf_path, (str, Path)):
                self.logger.error(f"Invalid pdf_path: {pdf_path}")
                return []

            # 初始化页面特征分析器（适配器，禁用详细日志避免重复输出�?
            try:
                feature_analyzer = PageFeatureAnalyzer(page, enable_logging=False)
            except Exception as e:
                self.logger.error(f"Failed to initialize PageFeatureAnalyzer: {e}")
                return []
            
            # 获取处理方法和参�?
            method = self.params.get("table_method", "mixed").lower()
            if method not in ['camelot', 'pdfplumber', 'mixed']:
                self.logger.error(f"Invalid table_method: {method}. Must be one of: camelot, pdfplumber, mixed")
                return []
            
            flavor = self.params.get("table_flavor", None)
            score_threshold = self.params.get("table_score_threshold", 0.5)
            
            # 验证score_threshold范围
            if not isinstance(score_threshold, (int, float)) or score_threshold < 0 or score_threshold > 1:
                self.logger.warning(f"Invalid score_threshold: {score_threshold}. Using default 0.5")
                score_threshold = 0.5
            
            page_num = getattr(page, "page_number", 1)
            
            # #region agent log
            write_debug_log(
                location="table_processor.py:176",
                message="method and params extracted",
                data={
                    "method": method,
                    "flavor": flavor,
                    "score_threshold": score_threshold,
                    "page_num": page_num
                },
                hypothesis_id="E"
            )
            # #endregion
            
            # 获取预测的表格类�?
            try:
                predicted_table_type = feature_analyzer.predict_table_type()
                
                # #region agent log
                write_debug_log(
                    location="table_processor.py:193",
                    message="table type predicted",
                    data={"predicted_table_type": predicted_table_type},
                    hypothesis_id="D"
                )
                # #endregion
            except Exception as e:
                self.logger.error(f"Failed to predict table type: {e}")
                return []
            
            # 自动检测表格类型和flavor
            if flavor is None:
                try:
                    if method == "pdfplumber":
                        flavor = "lines" if predicted_table_type == "bordered" else "text"
                    elif method == "camelot":
                        flavor = "lattice" if predicted_table_type == "bordered" else "stream"
                    else:  # mixed method
                        flavor = "auto"
                    
                    # #region agent log
                    write_debug_log(
                        location="table_processor.py:199",
                        message="flavor auto-selected",
                        data={
                            "method": method,
                            "predicted_table_type": predicted_table_type,
                            "selected_flavor": flavor
                        },
                        hypothesis_id="E"
                    )
                    # #endregion
                except Exception as e:
                    self.logger.error(f"Failed to set flavor: {e}")
                    return []
            else:
                # 检查用户手动设置的flavor是否与预测类型匹�?
                is_mismatch = False
                if method == "pdfplumber":
                    # pdfplumber: "lines"对应"bordered"�?text"对应"unbordered"
                    if (flavor == "lines" and predicted_table_type != "bordered") or \
                       (flavor == "text" and predicted_table_type != "unbordered"):
                        is_mismatch = True
                elif method == "camelot":
                    # camelot: "lattice"对应"bordered"�?stream"对应"unbordered"
                    if (flavor == "lattice" and predicted_table_type != "bordered") or \
                       (flavor == "stream" and predicted_table_type != "unbordered"):
                        is_mismatch = True
                
                # #region agent log
                write_debug_log(
                    location="table_processor.py:210",
                    message="flavor mismatch check",
                    data={
                        "method": method,
                        "flavor": flavor,
                        "predicted_table_type": predicted_table_type,
                        "is_mismatch": is_mismatch
                    },
                    hypothesis_id="E"
                )
                # #endregion
                
                if is_mismatch:
                    # 生成建议的flavor
                    if method == "pdfplumber":
                        suggested_flavor = "lines" if predicted_table_type == "bordered" else "text"
                    elif method == "camelot":
                        suggested_flavor = "lattice" if predicted_table_type == "bordered" else "stream"
                    else:
                        suggested_flavor = "auto"
                    
                    self.logger.warning(
                        f"[TableProcessor] ⚠️ Flavor设置与预测类型不匹配�?
                        f" 预测类型: {predicted_table_type}, 设置的Flavor: {flavor}, "
                        f"建议Flavor: {suggested_flavor} (页面 {page_num})"
                    )
            
            self.logger.info(f"[TableProcessor] Method: {method}, Flavor: {flavor}, Predicted Table type: {predicted_table_type} on page {page_num}")
            
            # 根据方法和flavor处理
            try:
                # #region agent log
                write_debug_log(
                    location="table_processor.py:242",
                    message="starting table extraction",
                    data={
                        "method": method,
                        "flavor": flavor,
                        "score_threshold": score_threshold
                    },
                    hypothesis_id="E"
                )
                # #endregion
                
                if method == "pdfplumber":
                    results = self._process_pdfplumber(page, feature_analyzer, flavor, score_threshold)
                elif method == "camelot":
                    results = self._process_camelot(pdf_path, page, feature_analyzer, flavor, score_threshold)
                elif method == "mixed":
                    results = self._process_mixed(pdf_path, page, feature_analyzer, score_threshold)
                else:
                    self.logger.error(f"Unknown table extraction method: {method}")
                    return []
                
                # #region agent log
                write_debug_log(
                    location="table_processor.py:252",
                    message="table extraction completed",
                    data={
                        "method": method,
                        "tables_found": len(results),
                        "results": [{"score": r.get("score"), "source": r.get("source")} for r in results[:3]]
                    },
                    hypothesis_id="E"
                )
                # #endregion
                
                return results
            except Exception as e:
                self.logger.error(f"Error during table processing: {e}")
                return []
                
        except Exception as e:
            self.logger.error(f"Unexpected error in process_pdf_page: {e}")
            return []
    
    def _process_pdfplumber(self, page, feature_analyzer, flavor, score_threshold):
        """使用pdfplumber处理页面"""
        try:
            extractor = ExtractorFactory.create('pdfplumber')
        except ValueError as e:
            self.logger.error(f"Failed to create PDFPlumber extractor: {e}")
            return []
        
        # 准备参数
        extract_params = {
            'flavor': flavor,
            'param_mode': self.params.get('pdfplumber_param_mode', 'auto'),
            'pdfplumber_custom_params': self.params.get('pdfplumber_custom_params'),
            'score_threshold': score_threshold
        }
        
        # 提取表格
        results = extractor.extract_tables(page, feature_analyzer, extract_params)
        return results

    def _process_camelot(self, pdf_path, page, feature_analyzer, flavor, score_threshold):
        """使用camelot处理页面"""
        try:
            extractor = ExtractorFactory.create('camelot')
        except ValueError as e:
            self.logger.error(f"Failed to create Camelot extractor: {e}")
            return []
        
        page_num = getattr(page, "page_number", 1)
        
        # 准备参数
        extract_params = {
            'pdf_path': pdf_path,
            'page_num': page_num,
            'flavor': flavor,
            'param_mode': self.params.get('camelot_lattice_param_mode', self.params.get('camelot_stream_param_mode', 'auto')),
            'camelot_lattice_custom_params': self.params.get('camelot_lattice_custom_params'),
            'camelot_stream_custom_params': self.params.get('camelot_stream_custom_params'),
            'score_threshold': score_threshold,
            'table_areas': self.params.get('table_areas')
        }
        
        # 提取表格
        results = extractor.extract_tables(page, feature_analyzer, extract_params)
        return results

    def _process_mixed(self, pdf_path, page, feature_analyzer, score_threshold):
        """使用混合方法处理页面"""
        try:
            pdfplumber_extractor = ExtractorFactory.create('pdfplumber')
            camelot_extractor = ExtractorFactory.create('camelot')
        except ValueError as e:
            self.logger.error(f"Failed to create extractors: {e}")
            return []
        
        # 第一轮：pdfplumber检�?
        pdfplumber_params_lines = {
            'flavor': 'lines',
            'param_mode': self.params.get('pdfplumber_param_mode', 'auto'),
            'pdfplumber_custom_params': self.params.get('pdfplumber_custom_params'),
            'score_threshold': 0.0  # 先不过滤，后面统一过滤
        }
        pdfplumber_params_text = {
            'flavor': 'text',
            'param_mode': self.params.get('pdfplumber_param_mode', 'auto'),
            'pdfplumber_custom_params': self.params.get('pdfplumber_custom_params'),
            'score_threshold': 0.0
        }
        
        pdfplumber_lines = pdfplumber_extractor.extract_tables(page, feature_analyzer, pdfplumber_params_lines)
        pdfplumber_text = pdfplumber_extractor.extract_tables(page, feature_analyzer, pdfplumber_params_text)
        all_pdfplumber = pdfplumber_lines + pdfplumber_text
        
        # 获取高分区域用于camelot精细�?
        high_score_bboxes = [r["bbox"] for r in all_pdfplumber if r["score"] > 0.7 and r["bbox"] is not None]
        page_num = getattr(page, "page_number", 1)
        
        # 第二轮：camelot精细�?
        camelot_results = []
        if high_score_bboxes:
            table_type = feature_analyzer.predict_table_type()
            camelot_params = {
                'pdf_path': pdf_path,
                'page_num': page_num,
                'flavor': 'lattice' if table_type == "bordered" else 'stream',
                'param_mode': self.params.get('camelot_lattice_param_mode', self.params.get('camelot_stream_param_mode', 'auto')),
                'camelot_lattice_custom_params': self.params.get('camelot_lattice_custom_params'),
                'camelot_stream_custom_params': self.params.get('camelot_stream_custom_params'),
                'score_threshold': 0.0,
                'table_areas': high_score_bboxes
            }
            camelot_results = camelot_extractor.extract_tables(page, feature_analyzer, camelot_params)
        
        # 合并和去�?
        all_results = all_pdfplumber + camelot_results
        unique_tables = {}
        for item in all_results:
            bbox_key = tuple(np.round(item['bbox'], 2)) if item['bbox'] is not None else None
            if bbox_key not in unique_tables or item['score'] > unique_tables[bbox_key]['score']:
                unique_tables[bbox_key] = item
        
        final_tables = [v for v in unique_tables.values() if v['score'] >= score_threshold]
        self.logger.debug(f"[TableProcessor] Final tables after deduplication and thresholding: {len(final_tables)}")
        return final_tables

    def extract_pdfplumber_lines(self, page, feature_analyzer=None) -> list:
        """使用pdfplumber lines模式提取有框表格"""
        evaluator = TableEvaluator()
        evaluator.source = "pdfplumber"
        evaluator.flavor = "lines"

        if feature_analyzer is None:
            feature_analyzer = PageFeatureAnalyzer(page, enable_logging=False)
        
        # Get parameters based on mode (default/auto/custom)
        param_mode = self.params.get('pdfplumber_param_mode', 'auto')
        if param_mode == 'custom' and 'pdfplumber_custom_params' in self.params:
            params = self.params['pdfplumber_custom_params'].copy()
        elif param_mode == 'default':
            from docuvision_core.utils.param_config import get_default_pdfplumber_params
            params = get_default_pdfplumber_params()
        else:  # auto
            params = feature_analyzer.get_pdfplumber_params('bordered')
        
        tables = page.find_tables(params)
        
        self.logger.info(f"[TableProcessor] PDFPlumber (lines) detected {len(tables)} tables on page {getattr(page, 'page_number', '?')}")
        self.logger.debug(f"[TableProcessor] Using parameters: {params}")
        
        results = []
        for idx, p_table in enumerate(tables):
            wrapper = PDFPlumberTableWrapper(p_table, page) 
            p_score, p_details, p_domain = evaluator.evaluate(wrapper)
            self.logger.info(f"[TableProcessor] PDFPlumber lines table {idx+1}: score={p_score:.3f}, domain={p_domain}, bbox={getattr(p_table, 'bbox', None)}")
            results.append({
                'table': wrapper,
                'bbox': p_table.bbox,
                'score': p_score,
                'details': p_details,
                'domain': p_domain,
                'source': 'pdfplumber_lines'
            })
        return results

    def extract_pdfplumber_text(self, page, feature_analyzer=None) -> list:
        """使用pdfplumber text模式提取无框表格"""
        evaluator = TableEvaluator()
        evaluator.source = "pdfplumber"
        evaluator.flavor = "text"

        if feature_analyzer is None:
            feature_analyzer = PageFeatureAnalyzer(page, enable_logging=False)
        
        # Get parameters based on mode (default/auto/custom)
        param_mode = self.params.get('pdfplumber_param_mode', 'auto')
        if param_mode == 'custom' and 'pdfplumber_custom_params' in self.params:
            params = self.params['pdfplumber_custom_params'].copy()
        elif param_mode == 'default':
            from docuvision_core.utils.param_config import get_default_pdfplumber_params
            params = get_default_pdfplumber_params()
        else:  # auto
            params = feature_analyzer.get_pdfplumber_params('unbordered')
        
        tables = page.find_tables(params)
        
        self.logger.info(f"[TableProcessor] PDFPlumber (text) detected {len(tables)} tables on page {getattr(page, 'page_number', '?')}")
        self.logger.debug(f"[TableProcessor] Using parameters: {params}")
        
        results = []
        for idx, p_table in enumerate(tables):
            wrapper = PDFPlumberTableWrapper(p_table, page)
            p_score, p_details, p_domain = evaluator.evaluate(wrapper)
            self.logger.info(f"[TableProcessor] PDFPlumber text table {idx+1}: score={p_score:.3f}, domain={p_domain}, bbox={getattr(p_table, 'bbox', None)}")
            results.append({
                'table': wrapper,
                'bbox': p_table.bbox,
                'score': p_score,
                'details': p_details,
                'domain': p_domain,
                'source': 'pdfplumber_text'
            })
        return results

    def extract_camelot_lattice(self, pdf_path, page_num, page, feature_analyzer=None, table_areas=None) -> list:
        """使用Camelot lattice模式提取表格"""
        # 延迟导入camelot，避免在模块导入时因系统依赖问题导致应用启动失败
        # 在导入camelot之前设置环境变量，避免在无头环境中加载OpenGL�?
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ.setdefault('DISPLAY', '')
        os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '0')
        os.environ.setdefault('MESA_GL_VERSION_OVERRIDE', '3.3')
        
        try:
            import camelot
        except ImportError as e:
            self.logger.error(f"Failed to import camelot: {e}. Camelot may not be available in this environment.")
            return []
        except Exception as e:
            # libGL.so.1错误通常是警告性的，camelot在headless模式下仍可使�?
            error_str = str(e).lower()
            if 'libgl' in error_str or 'opengl' in error_str or 'libgl.so' in error_str:
                self.logger.warning(f"Camelot import warning (libGL/OpenGL): {e}. Attempting to continue...")
                try:
                    import camelot
                except:
                    self.logger.error(f"Camelot import failed after retry: {e}")
                    return []
            else:
                self.logger.error(f"Unexpected error importing camelot: {e}")
                return []
        
        evaluator = TableEvaluator()
        evaluator.source = "camelot"
        evaluator.flavor = "lattice"

        if feature_analyzer is None:
            feature_analyzer = PageFeatureAnalyzer(page, enable_logging=False)
        
        image_shape = (int(page.height * 2), int(page.width * 2))
        
        # Get parameters based on mode (default/auto/custom)
        param_mode = self.params.get('camelot_lattice_param_mode', 'auto')
        if param_mode == 'custom' and 'camelot_lattice_custom_params' in self.params:
            params = self.params['camelot_lattice_custom_params'].copy()
            # Ensure flavor is set for custom params
            if 'flavor' not in params:
                params['flavor'] = 'lattice'
        elif param_mode == 'default':
            from docuvision_core.utils.param_config import get_default_camelot_lattice_params
            params = get_default_camelot_lattice_params()
        else:  # auto
            params = feature_analyzer.get_camelot_lattice_params(image_shape)
            # Ensure flavor is set
            if 'flavor' not in params:
                params['flavor'] = 'lattice'
        
        params['pages'] = str(page_num)
        self.logger.info(f"[TableProcessor] Using camelot lattice parameters: {params}")
        
        if table_areas:
            params['table_areas'] = [",".join(map(str, area)) for area in table_areas]
        
        self.logger.debug(f"[TableProcessor] Using lattice parameters: {params}")
        
        try:
            camelot_tables = camelot.read_pdf(pdf_path, **params)
        except Exception as e:
            self.logger.error(f"Camelot lattice extraction failed: {str(e)}")
            return []
        
        self.logger.info(f"[TableProcessor] Camelot (lattice) detected {len(camelot_tables)} tables on page {page_num}")
        results = []
        for idx, ct in enumerate(camelot_tables):
            en_ct = evaluator.enhance_camelot_features(ct)
            c_score, c_details, c_domain = evaluator.evaluate(en_ct)
            self.logger.info(f"[TableProcessor] Camelot lattice table {idx+1}: score={c_score:.3f}, domain={c_domain}, bbox={getattr(en_ct, 'bbox', None)}")
            results.append({
                'table': en_ct,
                'bbox': getattr(en_ct, 'bbox', None),
                'score': c_score,
                'details': c_details,
                'domain': c_domain,
                'source': 'camelot_lattice'
            })
        return results


    def extract_camelot_stream(self, pdf_path, page_num, page, feature_analyzer=None, table_areas=None) -> list:
        """使用Camelot stream模式提取表格"""
        # 延迟导入camelot，避免在模块导入时因系统依赖问题导致应用启动失败
        # 在导入camelot之前设置环境变量，避免在无头环境中加载OpenGL�?
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ.setdefault('DISPLAY', '')
        os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '0')
        os.environ.setdefault('MESA_GL_VERSION_OVERRIDE', '3.3')
        
        try:
            import camelot
        except ImportError as e:
            self.logger.error(f"Failed to import camelot: {e}. Camelot may not be available in this environment.")
            return []
        except Exception as e:
            # libGL.so.1错误通常是警告性的，camelot在headless模式下仍可使�?
            error_str = str(e).lower()
            if 'libgl' in error_str or 'opengl' in error_str or 'libgl.so' in error_str:
                self.logger.warning(f"Camelot import warning (libGL/OpenGL): {e}. Attempting to continue...")
                try:
                    import camelot
                except:
                    self.logger.error(f"Camelot import failed after retry: {e}")
                    return []
            else:
                self.logger.error(f"Unexpected error importing camelot: {e}")
                return []
        
        evaluator = TableEvaluator()
        evaluator.source = "camelot"
        evaluator.flavor = "stream"

        if feature_analyzer is None:
            feature_analyzer = PageFeatureAnalyzer(page, enable_logging=False)
        
        # Get parameters based on mode (default/auto/custom)
        param_mode = self.params.get('camelot_stream_param_mode', 'auto')
        if param_mode == 'custom' and 'camelot_stream_custom_params' in self.params:
            params = self.params['camelot_stream_custom_params'].copy()
            # Ensure flavor is set for custom params
            if 'flavor' not in params:
                params['flavor'] = 'stream'
        elif param_mode == 'default':
            from docuvision_core.utils.param_config import get_default_camelot_stream_params
            params = get_default_camelot_stream_params()
        else:  # auto
            params = feature_analyzer.get_camelot_stream_params()
            # Ensure flavor is set
            if 'flavor' not in params:
                params['flavor'] = 'stream'
        
        params['pages'] = str(page_num)
        
        if table_areas:
            params['table_areas'] = [",".join(map(str, area)) for area in table_areas]
        
        self.logger.debug(f"[TableProcessor] Using stream parameters: {params}")
        
        try:
            camelot_tables = camelot.read_pdf(pdf_path, **params)
        except Exception as e:
            self.logger.error(f"Camelot stream extraction failed: {str(e)}")
            return []
        
        self.logger.info(f"[TableProcessor] Camelot (stream) detected {len(camelot_tables)} tables on page {page_num}")
        results = []
        for idx, ct in enumerate(camelot_tables):
            en_ct = evaluator.enhance_camelot_features(ct)
            c_score, c_details, c_domain = evaluator.evaluate(en_ct)
            self.logger.info(f"[TableProcessor] Camelot stream table {idx+1}: score={c_score:.3f}, domain={c_domain}, bbox={getattr(en_ct, 'bbox', None)}")
            results.append({
                'table': en_ct,
                'bbox': getattr(en_ct, 'bbox', None),
                'score': c_score,
                'details': c_details,
                'domain': c_domain,
                'source': 'camelot_stream'
            })
        return results
