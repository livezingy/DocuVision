# core/processing/table_processor.py
"""table processor module."""

from typing import Dict, List, Optional, Any
from pathlib import Path
from PIL import Image
import time
import numpy as np
import pandas as pd
import pdfplumber
# Comment.
# Comment.

from docuvision_core.utils.logger import AppLogger
# Comment.
# Comment.
# Comment.
from docuvision_core.processing.table_evaluator import TableEvaluator, PDFPlumberTableWrapper

# Comment.
from docuvision_core.processing.page_feature_analyzer import PageFeatureAnalyzer as FeatureAnalyzer
from docuvision_core.processing.table_type_classifier import TableTypeClassifier
from docuvision_core.processing.table_params_calculator import TableParamsCalculator

# Comment.
from docuvision_core.extractors.factory import ExtractorFactory


def _bbox_area(bbox: Optional[tuple]) -> float:
    if not bbox or len(bbox) < 4:
        return 0.0
    x0, top, x1, bottom = bbox[:4]
    return max(0.0, float(x1) - float(x0)) * max(0.0, float(bottom) - float(top))


def _bbox_overlap_ratio(a: tuple, b: tuple) -> float:
    ax0, atop, ax1, abottom = a[:4]
    bx0, btop, bx1, bbottom = b[:4]
    ix0 = max(ax0, bx0)
    iy0 = max(atop, btop)
    ix1 = min(ax1, bx1)
    iy1 = min(abottom, bbottom)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    intersection = (ix1 - ix0) * (iy1 - iy0)
    min_area = min(_bbox_area(a), _bbox_area(b))
    if min_area <= 0:
        return 0.0
    return intersection / min_area


def _dedupe_overlapping_tables(
    tables: List[Dict[str, Any]],
    overlap_threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """Drop lower-scoring tables whose bbox overlaps an already kept table."""
    ranked = sorted(tables, key=lambda item: float(item.get("score") or 0.0), reverse=True)
    kept: List[Dict[str, Any]] = []
    for item in ranked:
        bbox = item.get("bbox")
        if bbox is None:
            kept.append(item)
            continue
        overlaps = False
        for existing in kept:
            existing_bbox = existing.get("bbox")
            if existing_bbox and _bbox_overlap_ratio(tuple(bbox), tuple(existing_bbox)) >= overlap_threshold:
                overlaps = True
                break
        if not overlaps:
            kept.append(item)
    return kept


class PageFeatureAnalyzer:
    """Docstring."""
    
    def __init__(self, page, enable_logging=True):
        """Docstring."""
        self.page = page
        self.logger = AppLogger.get_logger()
        
        # Comment.
        self._feature_analyzer = FeatureAnalyzer(page, enable_logging=enable_logging)
        self._classifier = TableTypeClassifier(self._feature_analyzer, page)
        self._calculator = TableParamsCalculator(self._feature_analyzer)
    
    # Comment.
    
    @property
    def char_analysis(self) -> dict:
        """Docstring."""
        return self._feature_analyzer.char_analysis
    
    @property
    def line_analysis(self) -> dict:
        """Docstring."""
        return self._feature_analyzer.line_analysis
    
    @property
    def text_line_analysis(self) -> dict:
        """Docstring."""
        return self._feature_analyzer.text_line_analysis
    
    @property
    def word_analysis(self) -> dict:
        """Docstring."""
        return self._feature_analyzer.word_analysis
    
    # Comment.
    
    def predict_table_type(self) -> str:
        """Docstring."""
        return self._classifier.predict_table_type()

    def classify_table_type(self) -> dict:
        """Return table type classification with detailed metrics."""
        return self._classifier.classify()
    
    def get_pdfplumber_params(self, table_type: str = 'bordered') -> dict:
        """Docstring."""
        return self._calculator.get_pdfplumber_params(table_type)
    
    def get_camelot_lattice_params(self, image_shape=None) -> dict:
        """Docstring."""
        return self._calculator.get_camelot_lattice_params(image_shape)
    
    def get_camelot_stream_params(self) -> dict:
        """Docstring."""
        return self._calculator.get_camelot_stream_params()


class TableProcessor:
    """Docstring."""
    
    def __init__(self, params: Optional[Dict] = None):
        self.logger = AppLogger.get_logger()
        self.params = params or {}
        self.models = self.params.get('models')


    def process_pdf_page(self, pdf_path, page):
        """Docstring."""
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
            # Comment.
            if not page:
                self.logger.error("Page object is None")
                return []
            
            if not pdf_path or not isinstance(pdf_path, (str, Path)):
                self.logger.error(f"Invalid pdf_path: {pdf_path}")
                return []

            # Comment.
            try:
                feature_analyzer = PageFeatureAnalyzer(page, enable_logging=False)
            except Exception as e:
                self.logger.error(f"Failed to initialize PageFeatureAnalyzer: {e}")
                return []
            
            # Comment.
            method = self.params.get("table_method", "mixed").lower()
            if method not in ['camelot', 'pdfplumber', 'mixed']:
                self.logger.error(f"Invalid table_method: {method}. Must be one of: camelot, pdfplumber, mixed")
                return []
            
            flavor = self.params.get("table_flavor", None)
            score_threshold = self.params.get("table_score_threshold", 0.5)
            
            # Comment.
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
            
            # Comment.
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
            
            # Comment.
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
                # Comment.
                is_mismatch = False
                if method == "pdfplumber":
                    # Comment.
                    if (flavor == "lines" and predicted_table_type != "bordered") or \
                       (flavor == "text" and predicted_table_type != "unbordered"):
                        is_mismatch = True
                elif method == "camelot":
                    # Comment.
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
                    # Comment.
                    if method == "pdfplumber":
                        suggested_flavor = "lines" if predicted_table_type == "bordered" else "text"
                    elif method == "camelot":
                        suggested_flavor = "lattice" if predicted_table_type == "bordered" else "stream"
                    else:
                        suggested_flavor = "auto"
                    
                    self.logger.warning(
                    )
            
            self.logger.info(f"[TableProcessor] Method: {method}, Flavor: {flavor}, Predicted Table type: {predicted_table_type} on page {page_num}")
            
            # Comment.
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
        """Docstring."""
        try:
            extractor = ExtractorFactory.create('pdfplumber')
        except ValueError as e:
            self.logger.error(f"Failed to create PDFPlumber extractor: {e}")
            return []
        
        # Comment.
        extract_params = {
            'flavor': flavor,
            'param_mode': self.params.get('pdfplumber_param_mode', 'auto'),
            'pdfplumber_custom_params': self.params.get('pdfplumber_custom_params'),
            'score_threshold': score_threshold
        }
        
        # Comment.
        results = extractor.extract_tables(page, feature_analyzer, extract_params)
        return results

    def _process_camelot(self, pdf_path, page, feature_analyzer, flavor, score_threshold):
        """Docstring."""
        try:
            extractor = ExtractorFactory.create('camelot')
        except ValueError as e:
            self.logger.error(f"Failed to create Camelot extractor: {e}")
            return []
        
        page_num = getattr(page, "page_number", 1)
        
        # Comment.
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
        
        # Comment.
        results = extractor.extract_tables(page, feature_analyzer, extract_params)
        return results

    def _process_mixed(self, pdf_path, page, feature_analyzer, score_threshold):
        """Docstring."""
        try:
            pdfplumber_extractor = ExtractorFactory.create('pdfplumber')
            camelot_extractor = ExtractorFactory.create('camelot')
        except ValueError as e:
            self.logger.error(f"Failed to create extractors: {e}")
            return []
        
        # Comment.
        pdfplumber_params_lines = {
            'flavor': 'lines',
            'param_mode': self.params.get('pdfplumber_param_mode', 'auto'),
            'pdfplumber_custom_params': self.params.get('pdfplumber_custom_params'),
            'score_threshold': 0.0
        }
        pdfplumber_params_text = {
            'flavor': 'text',
            'param_mode': self.params.get('pdfplumber_param_mode', 'auto'),
            'pdfplumber_custom_params': self.params.get('pdfplumber_custom_params'),
            'score_threshold': 0.0
        }

        table_type = feature_analyzer.predict_table_type()
        primary_params = pdfplumber_params_lines if table_type == "bordered" else pdfplumber_params_text
        fallback_params = pdfplumber_params_text if table_type == "bordered" else pdfplumber_params_lines

        all_pdfplumber = pdfplumber_extractor.extract_tables(page, feature_analyzer, primary_params)
        if not all_pdfplumber:
            all_pdfplumber = pdfplumber_extractor.extract_tables(page, feature_analyzer, fallback_params)
        all_pdfplumber = _dedupe_overlapping_tables(all_pdfplumber)

        page_num = getattr(page, "page_number", 1)
        fallback_threshold = self.params.get('smart_camelot_fallback_threshold', 0.8)
        max_pdfplumber_score = max((r["score"] for r in all_pdfplumber), default=0.0)

        camelot_results = []
        if max_pdfplumber_score < fallback_threshold:
            camelot_params = {
                'pdf_path': pdf_path,
                'page_num': page_num,
                'flavor': 'lattice' if table_type == "bordered" else 'stream',
                'param_mode': self.params.get('camelot_lattice_param_mode', self.params.get('camelot_stream_param_mode', 'auto')),
                'camelot_lattice_custom_params': self.params.get('camelot_lattice_custom_params'),
                'camelot_stream_custom_params': self.params.get('camelot_stream_custom_params'),
                'score_threshold': 0.0,
            }
            camelot_results = camelot_extractor.extract_tables(page, feature_analyzer, camelot_params)
        
        # Comment.
        all_results = all_pdfplumber + camelot_results
        all_results = _dedupe_overlapping_tables(all_results)
        unique_tables = {}
        for item in all_results:
            bbox_key = tuple(np.round(item['bbox'], 2)) if item['bbox'] is not None else None
            if bbox_key not in unique_tables or item['score'] > unique_tables[bbox_key]['score']:
                unique_tables[bbox_key] = item
        
        final_tables = [v for v in unique_tables.values() if v['score'] >= score_threshold]
        self.logger.debug(f"[TableProcessor] Final tables after deduplication and thresholding: {len(final_tables)}")
        return final_tables

    def extract_pdfplumber_lines(self, page, feature_analyzer=None) -> list:
        """Docstring."""
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
        """Docstring."""
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
        """Docstring."""
        # Comment.
        # Comment.
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
            # Comment.
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
        """Docstring."""
        # Comment.
        # Comment.
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
            # Comment.
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
