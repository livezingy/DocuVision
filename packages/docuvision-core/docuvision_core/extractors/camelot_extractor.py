# core/extractors/camelot_extractor.py
"""camelot extractor module."""

import os
import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from docuvision_core.extractors.base import BaseExtractor
from docuvision_core.processing.table_evaluator import TableEvaluator
from docuvision_core.utils.logger import AppLogger


class CamelotExtractor(BaseExtractor):
    """Docstring."""
    
    def __init__(self, **kwargs):
        """Docstring."""
        self.logger = AppLogger.get_logger()
        # Comment.
        # Comment.
        self._camelot = None
        self._camelot_import_attempted = False
    
    def _ensure_camelot_imported(self):
        """Docstring."""
        if self._camelot is not None:
            return True
        
        if self._camelot_import_attempted:
            return False
        
        # Comment.
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ.setdefault('DISPLAY', '')
        os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '0')
        # Comment.
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
            # Comment.
            error_str = str(e).lower()
            if 'libgl' in error_str or 'opengl' in error_str:
                # Comment.
                self.logger.warning(f"Camelot import warning (libGL/OpenGL): {e}. Camelot may still work in headless mode.")
                try:
                    # Comment.
                    import camelot
                    self._camelot = camelot
                    return True
                except:
                    # Comment.
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
        """Docstring."""
        return "camelot"
    
    @property
    def supported_flavors(self) -> List[str]:
        """Docstring."""
        return ['lattice', 'stream']
    
    def calculate_params(self, feature_analyzer, table_type: str, **kwargs) -> Dict:
        """Docstring."""
        flavor = kwargs.get('flavor')
        if flavor is None:
            # Comment.
            flavor = 'lattice' if table_type == 'bordered' else 'stream'
        
        if flavor == 'lattice':
            return self._calculate_lattice_params(feature_analyzer, **kwargs)
        elif flavor == 'stream':
            return self._calculate_stream_params(feature_analyzer)
        else:
            raise ValueError(f"Unsupported flavor: {flavor}")
    
    def _calculate_lattice_params(self, feature_analyzer, **kwargs) -> Dict:
        """Docstring."""
        from docuvision_core.processing.table_params_calculator import TableParamsCalculator
        
        calculator = TableParamsCalculator(feature_analyzer)
        image_shape = kwargs.get('image_shape')
        return calculator.get_camelot_lattice_params(image_shape)
    
    def _calculate_stream_params(self, feature_analyzer) -> Dict:
        """Docstring."""
        from docuvision_core.processing.table_params_calculator import TableParamsCalculator
        
        calculator = TableParamsCalculator(feature_analyzer)
        return calculator.get_camelot_stream_params()
    
    def extract_tables(self, page, feature_analyzer, params: Dict) -> List[Dict]:
        """Docstring."""
        # Comment.
        if not self._ensure_camelot_imported():
            self.logger.error("Camelot is not available")
            return []
        
        # Comment.
        pdf_path = params.get('pdf_path')
        page_num = params.get('page_num')
        
        if pdf_path is None or page_num is None:
            self.logger.error("pdf_path and page_num are required for Camelot extraction")
            return []
        
        flavor = params.get('flavor')
        if flavor is None:
            # Comment.
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
        """Docstring."""
        evaluator = TableEvaluator()
        evaluator.source = "camelot"
        evaluator.flavor = "lattice"
        
        # Comment.
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
        
        # Comment.
        extract_params['flavor'] = 'lattice'
        extract_params['pages'] = str(page_num)
        
        # Comment.
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
        
        # Comment.
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
        """Docstring."""
        evaluator = TableEvaluator()
        evaluator.source = "camelot"
        evaluator.flavor = "stream"
        
        # Comment.
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
        
        # Comment.
        extract_params['flavor'] = 'stream'
        extract_params['pages'] = str(page_num)
        
        # Comment.
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
        
        # Comment.
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
