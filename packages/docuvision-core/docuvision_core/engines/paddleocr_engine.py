# core/engines/paddleocr_engine.py
"""paddleocr engine module."""

import os
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from PIL import Image
from docuvision_core.engines.base import BaseOCREngine, BaseDetectionEngine
from docuvision_core.utils.logger import AppLogger

# Comment.
# Comment.
if 'DISABLE_MODEL_SOURCE_CHECK' not in os.environ:
    os.environ['DISABLE_MODEL_SOURCE_CHECK'] = 'True'


class PaddleOCREngine(BaseOCREngine, BaseDetectionEngine):
    """Docstring."""
    
    def __init__(self, 
                 use_angle_cls: bool = True,
                 lang: str = 'ch',
                 use_gpu: bool = False,
                 enable_mkldnn: bool = False,
                 table_model_dir: Optional[str] = None,
                 **kwargs):
        """
        
        Args:
        """
        self.logger = AppLogger.get_logger()
        self.use_angle_cls = use_angle_cls
        self.lang = lang
        self.use_gpu = use_gpu
        self.enable_mkldnn = enable_mkldnn
        self.table_model_dir = table_model_dir
        
        self._ocr = None
        self._structure_engine = None
        self._ocr_initialized = False
        self._structure_initialized = False
        self._is_ppstructure_v3 = False
    
    @property
    def name(self) -> str:
        """Docstring."""
        return "paddleocr"
    
    def initialize(self, **kwargs) -> bool:
        """Docstring."""
        if self._ocr_initialized and self._ocr is not None:
            return True
        
        try:
            from paddleocr import PaddleOCR
            
            use_angle_cls = kwargs.get('use_angle_cls', self.use_angle_cls)
            lang = kwargs.get('lang', self.lang)
            use_gpu = kwargs.get('use_gpu', self.use_gpu)
            enable_mkldnn = kwargs.get('enable_mkldnn', self.enable_mkldnn)
            
            self._ocr = PaddleOCR(
                use_angle_cls=use_angle_cls,
                lang=lang,
                use_gpu=use_gpu,
                enable_mkldnn=enable_mkldnn
            )
            
            self._ocr_initialized = True
            self.logger.info(f"PaddleOCR engine initialized (lang={lang}, gpu={use_gpu})")
            return True
            
        except ImportError as e:
            self.logger.error(f"Failed to import PaddleOCR: {e}. Please install paddleocr: pip install paddleocr")
            return False
        except Exception as e:
            self.logger.error(f"Failed to initialize PaddleOCR engine: {e}")
            return False
    
    def load_models(self, **kwargs) -> bool:
        """Docstring."""
        if self._structure_initialized and self._structure_engine is not None:
            return True
        
        # Comment.
        ppstructure_v3_available = False
        try:
            from paddleocr import PPStructureV3
            ppstructure_v3_available = True
        except ImportError:
            pass
        
        if ppstructure_v3_available:
            # Comment.
            try:
                from paddleocr import PPStructureV3
                import paddleocr
                
                # Comment.
                try:
                    paddleocr_version = getattr(paddleocr, '__version__', 'unknown')
                    self.logger.info(f"PaddleOCR version: {paddleocr_version}")
                except:
                    pass
                
                # Comment.
                import inspect
                try:
                    sig = inspect.signature(PPStructureV3.__init__)
                    self.logger.info(f"PPStructureV3.__init__ signature: {sig}")
                    # Comment.
                    param_names = list(sig.parameters.keys())
                    self.logger.info(f"PPStructureV3 available parameters: {param_names}")
                    
                    # Comment.
                    if 'show_log' in param_names:
                        self.logger.warning("PPStructureV3.__init__ contains 'show_log' parameter - this should not be used")
                except Exception as sig_error:
                    self.logger.debug(f"Could not inspect PPStructureV3 signature: {sig_error}")
                
                # Comment.
                # Comment.
                init_success = False
                last_error = None
                
                # Comment.
                # Comment.
                try:
                    self._structure_engine = PPStructureV3(
                        use_doc_orientation_classify=False,
                        use_doc_unwarping=False,
                        use_textline_orientation=False,
                        use_seal_recognition=False,
                        use_formula_recognition=False,
                        use_chart_recognition=False,
                        use_region_detection=False,
                        use_table_recognition=True
                    )
                    self.logger.info("PaddleOCR PP-StructureV3 engine initialized (minimal config - table recognition only)")
                    init_success = True
                except (TypeError, ValueError) as e:
                    last_error = e
                    self.logger.debug(f"PPStructureV3(minimal config) failed: {e}")
                except Exception as e:
                    # Handle dependency errors specifically for Streamlit Cloud environment
                    if "DependencyError" in str(type(e)) or "paddlex" in str(e).lower():
                        self.logger.error(f"PPStructureV3 dependency error: {e}")
                        self.logger.error("Falling back to legacy PPStructure...")
                        # Try legacy PPStructure as fallback
                        return self._load_legacy_ppstructure(kwargs)
                    last_error = e
                    self.logger.debug(f"PPStructureV3(minimal config) failed with dependency error: {e}")
                
                # Comment.
                if not init_success:
                    try:
                        self._structure_engine = PPStructureV3(
                            use_doc_orientation_classify=False,
                            use_doc_unwarping=False
                        )
                        self.logger.info("PaddleOCR PP-StructureV3 engine initialized (with orientation/unwarping disabled)")
                        init_success = True
                    except (TypeError, ValueError) as e:
                        last_error = e
                        self.logger.debug(f"PPStructureV3(use_doc_orientation_classify=False, use_doc_unwarping=False) failed: {e}")
                    except Exception as e:
                        # Handle dependency errors specifically for Streamlit Cloud environment
                        if "DependencyError" in str(type(e)) or "paddlex" in str(e).lower():
                            self.logger.error(f"PPStructureV3 dependency error: {e}")
                            self.logger.error("Falling back to legacy PPStructure...")
                            # Try legacy PPStructure as fallback
                            return self._load_legacy_ppstructure(kwargs)
                        last_error = e
                        self.logger.debug(f"PPStructureV3(use_doc_orientation_classify=False, use_doc_unwarping=False) failed with dependency error: {e}")
                
                # Comment.
                if not init_success:
                    try:
                        self._structure_engine = PPStructureV3()
                        self.logger.info("PaddleOCR PP-StructureV3 engine initialized (default config - all features enabled)")
                        init_success = True
                    except (TypeError, ValueError) as e:
                        last_error = e
                        self.logger.debug(f"PPStructureV3() failed: {e}")
                    except Exception as e:
                        # Handle dependency errors specifically for Streamlit Cloud environment
                        if "DependencyError" in str(type(e)) or "paddlex" in str(e).lower():
                            self.logger.error(f"PPStructureV3 dependency error: {e}")
                            self.logger.error("Falling back to legacy PPStructure...")
                            # Try legacy PPStructure as fallback
                            return self._load_legacy_ppstructure(kwargs)
                        last_error = e
                        self.logger.debug(f"PPStructureV3() failed with dependency error: {e}")
                
                # Comment.
                if not init_success:
                    table_model_dir = kwargs.get('table_model_dir', self.table_model_dir)
                    if table_model_dir:
                        try:
                            self._structure_engine = PPStructureV3(
                                table_model_dir=table_model_dir,
                                use_doc_orientation_classify=False,
                                use_doc_unwarping=False,
                                use_formula_recognition=False,
                                use_chart_recognition=False
                            )
                            self.logger.info("PaddleOCR PP-StructureV3 engine initialized (with table_model_dir and minimal features)")
                            init_success = True
                        except (TypeError, ValueError) as e:
                            last_error = e
                            self.logger.debug(f"PPStructureV3(table_model_dir=...) failed: {e}")
                        except Exception as e:
                            # Handle dependency errors specifically for Streamlit Cloud environment
                            if "DependencyError" in str(type(e)) or "paddlex" in str(e).lower():
                                self.logger.error(f"PPStructureV3 dependency error: {e}")
                                self.logger.error("Falling back to legacy PPStructure...")
                                # Try legacy PPStructure as fallback
                                return self._load_legacy_ppstructure(kwargs)
                            last_error = e
                            self.logger.debug(f"PPStructureV3(table_model_dir=...) failed with dependency error: {e}")
                
                if not init_success:
                    error_msg = f"Failed to initialize PPStructureV3 with any parameter combination. Last error: {last_error}"
                    self.logger.error(error_msg)
                    if last_error:
                        self.logger.error(f"Error type: {type(last_error).__name__}, Error message: {str(last_error)}")
                    return False
                
                self._is_ppstructure_v3 = True
                self._structure_initialized = True
                self.logger.info("PaddleOCR PP-StructureV3 engine initialized successfully")
                return True
                
            except Exception as e:
                error_msg = f"Failed to load PP-StructureV3 models: {e}"
                self.logger.error(error_msg)
                import traceback
                self.logger.error(f"Full traceback:\n{traceback.format_exc()}")
                # Check if it's a dependency error and fall back to legacy version
                if "DependencyError" in str(type(e)) or "paddlex" in str(e).lower():
                    self.logger.error("Falling back to legacy PPStructure due to dependency issues...")
                    return self._load_legacy_ppstructure(kwargs)
                # Comment.
                return False
        else:
            # Comment.
            return self._load_legacy_ppstructure(kwargs)
    
    def _load_legacy_ppstructure(self, kwargs: Dict) -> bool:
        """Docstring."""
        try:
            from paddleocr import PPStructure
            
            table_model_dir = kwargs.get('table_model_dir', self.table_model_dir)
            
            init_params = {}
            if self.use_gpu:
                init_params['use_gpu'] = self.use_gpu
            if table_model_dir:
                init_params['table_model_dir'] = table_model_dir
            
            self._structure_engine = PPStructure(**init_params)
            self._is_ppstructure_v3 = False
            
            self._structure_initialized = True
            self.logger.info("PaddleOCR PP-Structure engine initialized (legacy version)")
            return True
            
        except ImportError as e:
            self.logger.error(f"Failed to import PPStructure: {e}")
            self.logger.error("Please ensure paddleocr is installed: pip install paddleocr")
            return False
        except Exception as e:
            self.logger.error(f"Failed to load PP-Structure models (legacy): {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    def recognize_text(self, image: Image.Image, **kwargs) -> List[Dict]:
        """Docstring."""
        if not self._ocr_initialized:
            if not self.initialize():
                return []
        
        if self._ocr is None:
            self.logger.error("PaddleOCR OCR is not available")
            return []
        
        try:
            # Comment.
            img_array = np.array(image)
            
            # Comment.
            det = kwargs.get('det', True)
            rec = kwargs.get('rec', True)
            cls = kwargs.get('cls', self.use_angle_cls)
            
            ocr_results = self._ocr.ocr(img_array, det=det, rec=rec, cls=cls)
            
            # Comment.
            results = []
            if ocr_results and ocr_results[0]:
                for line in ocr_results[0]:
                    if line:
                        bbox_points = line[0]
                        text_info = line[1]
                        
                        if text_info:
                            text = text_info[0]
                            confidence = text_info[1] if len(text_info) > 1 else 1.0
                            
                            # Comment.
                            x_coords = [point[0] for point in bbox_points]
                            y_coords = [point[1] for point in bbox_points]
                            x1, x2 = min(x_coords), max(x_coords)
                            y1, y2 = min(y_coords), max(y_coords)
                            
                            results.append({
                                'text': text,
                                'bbox': bbox_points,
                                'bbox_rect': [x1, y1, x2, y2],
                                'confidence': float(confidence)
                            })
            
            return results
            
        except Exception as e:
            self.logger.error(f"PaddleOCR recognition failed: {e}")
            return []
    
    def detect_tables(self, image: Image.Image, **kwargs) -> List[Dict]:
        """Docstring."""
        if not self._structure_initialized:
            if not self.load_models():
                return []
        
        if self._structure_engine is None:
            self.logger.error("PaddleOCR PP-Structure is not available")
            return []
        
        try:
            # Comment.
            img_array = np.array(image)
            
            # Comment.
            if self._is_ppstructure_v3:
                # Comment.
                # Comment.
                try:
                    # Comment.
                    results = self._structure_engine.predict(image)
                except (TypeError, AttributeError):
                    # Comment.
                    # Comment.
                    import cv2
                    img_array = np.array(image)
                    # Comment.
                    if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    results = self._structure_engine.predict(img_array)
                
                # Comment.
                detection_results = []
                for result in results:
                    # Comment.
                    # Comment.
                    result_type = None
                    if hasattr(result, 'type'):
                        result_type = result.type
                    elif hasattr(result, 'get') and isinstance(result, dict):
                        result_type = result.get('type')
                    
                    if result_type == 'table':
                        # Comment.
                        bbox = None
                        if hasattr(result, 'bbox'):
                            bbox = result.bbox
                        elif hasattr(result, 'get') and isinstance(result, dict):
                            bbox = result.get('bbox')
                        
                        if bbox:
                            if isinstance(bbox[0], (list, tuple)):
                                x_coords = [point[0] for point in bbox]
                                y_coords = [point[1] for point in bbox]
                                x1, y1 = min(x_coords), min(y_coords)
                                x2, y2 = max(x_coords), max(y_coords)
                                bbox_rect = [x1, y1, x2, y2]
                            else:
                                bbox_rect = bbox[:4] if len(bbox) >= 4 else bbox
                            
                            score = 1.0
                            if hasattr(result, 'score'):
                                score = result.score
                            elif hasattr(result, 'get') and isinstance(result, dict):
                                score = result.get('score', 1.0)
                            
                            detection_results.append({
                                'bbox': bbox_rect,
                                'confidence': float(score),
                                'type': 'table',
                                'raw': result
                            })
                
                return detection_results
            else:
                # Comment.
                # Comment.
                structure_results = self._structure_engine(img_array)
                
                # Comment.
                detection_results = []
                for item in structure_results:
                    if item.get('type') == 'table':
                        bbox = item.get('bbox', [])
                        if bbox and len(bbox) >= 4:
                            # Comment.
                            if isinstance(bbox[0], (list, tuple)):
                                # Comment.
                                x_coords = [point[0] for point in bbox]
                                y_coords = [point[1] for point in bbox]
                                x1, y1 = min(x_coords), min(y_coords)
                                x2, y2 = max(x_coords), max(y_coords)
                                bbox_rect = [x1, y1, x2, y2]
                            else:
                                # Comment.
                                bbox_rect = bbox[:4]
                            
                            detection_results.append({
                                'bbox': bbox_rect,
                                'confidence': item.get('score', 1.0),
                                'type': 'table',
                                'raw': item
                            })
                
                return detection_results
            
        except Exception as e:
            self.logger.error(f"PaddleOCR table detection failed: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return []
    
    def recognize_structure(self, image: Image.Image, table_bbox: Optional[List] = None, **kwargs) -> Dict:
        """Docstring."""
        if not self._structure_initialized:
            if not self.load_models():
                return {}
        
        if self._structure_engine is None:
            self.logger.error("PaddleOCR PP-Structure is not available")
            return {}
        
        try:
            # Comment.
            if table_bbox:
                x1, y1, x2, y2 = table_bbox
                image = image.crop((x1, y1, x2, y2))
            
            # Comment.
            if self._is_ppstructure_v3:
                # Comment.
                try:
                    # Comment.
                    results = self._structure_engine.predict(image)
                except (TypeError, AttributeError):
                    # Comment.
                    # Comment.
                    import cv2
                    img_array = np.array(image)
                    # Comment.
                    if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    results = self._structure_engine.predict(img_array)
                
                # Comment.
                table_result = None
                for result in results:
                    result_type = None
                    if hasattr(result, 'type'):
                        result_type = result.type
                    elif hasattr(result, 'get') and isinstance(result, dict):
                        result_type = result.get('type')
                    
                    if result_type == 'table':
                        table_result = result
                        break
                
                if not table_result:
                    self.logger.warning("No table structure found in image")
                    return {}
                
                # Comment.
                # Comment.
                html_content = ''
                if hasattr(table_result, 'html'):
                    html_content = table_result.html
                elif hasattr(table_result, 'get') and isinstance(table_result, dict):
                    html_content = table_result.get('html', '')
                
                # Comment.
                markdown_content = ''
                if hasattr(table_result, 'markdown'):
                    markdown_content = table_result.markdown
                elif hasattr(table_result, 'save_to_markdown'):
                    # Comment.
                    import tempfile
                    import os
                    tmp_path = None
                    try:
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as tmp_file:
                            tmp_path = tmp_file.name
                        table_result.save_to_markdown(save_path=tmp_path)
                        with open(tmp_path, 'r', encoding='utf-8') as f:
                            markdown_content = f.read()
                    except Exception as e:
                        self.logger.debug(f"Failed to extract markdown from PPStructureV3 result: {e}")
                    finally:
                        # Comment.
                        if tmp_path and os.path.exists(tmp_path):
                            try:
                                os.unlink(tmp_path)
                            except Exception as cleanup_error:
                                self.logger.warning(f"Failed to cleanup temporary file {tmp_path}: {cleanup_error}")
                
                cells = []
                if hasattr(table_result, 'cells'):
                    cells = table_result.cells
                elif hasattr(table_result, 'get') and isinstance(table_result, dict):
                    cells = table_result.get('cells', [])
                
                result = {
                    'html': html_content or markdown_content,
                    'cells': cells,
                    'raw': table_result if kwargs.get('return_raw', False) else None
                }
                
                if markdown_content:
                    result['markdown'] = markdown_content
            else:
                # Comment.
                # Comment.
                img_array = np.array(image)
                
                # Comment.
                structure_results = self._structure_engine(img_array)
                
                # Comment.
                table_result = None
                for item in structure_results:
                    if item.get('type') == 'table':
                        table_result = item
                        break
                
                if not table_result:
                    self.logger.warning("No table structure found in image")
                    return {}
                
                # Comment.
                result = {
                    'html': table_result.get('res', {}).get('html', ''),
                    'cells': table_result.get('res', {}).get('cells', []),
                    'raw': table_result if kwargs.get('return_raw', False) else None
                }
            
            # Comment.
            if result.get('html'):
                # Comment.
                result['has_structure'] = True
            elif result.get('cells'):
                # Comment.
                rows = set()
                cols = set()
                for cell in result['cells']:
                    if isinstance(cell, dict):
                        if 'row' in cell:
                            rows.add(cell['row'])
                        if 'col' in cell:
                            cols.add(cell['col'])
                result['rows'] = len(rows) if rows else 0
                result['columns'] = len(cols) if cols else 0
            
            return result
            
        except Exception as e:
            self.logger.error(f"PaddleOCR structure recognition failed: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return {}
    
    def recognize_text_in_region(self, image: Image.Image, bbox: List, **kwargs) -> List[Dict]:
        """Docstring."""
        try:
            # Comment.
            x1, y1, x2, y2 = bbox
            cropped = image.crop((x1, y1, x2, y2))
            
            # Comment.
            results = self.recognize_text(cropped, **kwargs)
            
            # Comment.
            for result in results:
                if 'bbox' in result:
                    # Comment.
                    adjusted_bbox = []
                    for point in result['bbox']:
                        adjusted_bbox.append([point[0] + x1, point[1] + y1])
                    result['bbox'] = adjusted_bbox
                
                if 'bbox_rect' in result:
                    # Comment.
                    rect = result['bbox_rect']
                    result['bbox_rect'] = [rect[0] + x1, rect[1] + y1, rect[2] + x1, rect[3] + y1]
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to recognize text in region: {e}")
            return []
    
    def is_available(self) -> bool:
        """Docstring."""
        try:
            import paddleocr
            return True
        except ImportError:
            return False
