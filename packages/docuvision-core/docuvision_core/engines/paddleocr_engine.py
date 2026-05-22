# core/engines/paddleocr_engine.py
"""
PaddleOCR引擎

封装PaddleOCR的OCR和PP-Structure表格检测功能
支持文本识别、表格检测和结构识别
"""

import os
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from PIL import Image
from docuvision_core.engines.base import BaseOCREngine, BaseDetectionEngine
from docuvision_core.utils.logger import AppLogger

# 设置环境变量以跳过模型源检查，加快初始化速度（特别是Streamlit Cloud环境！
# 这可以避免在初始化时检查模型托管服务器的连接怀
if 'DISABLE_MODEL_SOURCE_CHECK' not in os.environ:
    os.environ['DISABLE_MODEL_SOURCE_CHECK'] = 'True'


class PaddleOCREngine(BaseOCREngine, BaseDetectionEngine):
    """
    PaddleOCR引擎
    
    同时提供OCR和表格检测功能
    """
    
    def __init__(self, 
                 use_angle_cls: bool = True,
                 lang: str = 'ch',
                 use_gpu: bool = False,
                 enable_mkldnn: bool = False,
                 table_model_dir: Optional[str] = None,
                 **kwargs):
        """
        初始化PaddleOCR引擎
        
        Args:
            use_angle_cls: 是否使用角度分类噀
            lang: 语言！ch'（中文）成en'（英文）
            use_gpu: 是否使用GPU
            enable_mkldnn: 是否启用MKLDNN加速（CPU优化！
            table_model_dir: 表格模型目录（PP-Structure！
            **kwargs: 其他参数（预留）
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
        self._is_ppstructure_v3 = False  # 标记是否使用 PPStructureV3
    
    @property
    def name(self) -> str:
        """引擎名称"""
        return "paddleocr"
    
    def initialize(self, **kwargs) -> bool:
        """
        初始化OCR引擎
        
        Args:
            **kwargs: 初始化参敀
                - use_angle_cls: 是否使用角度分类噀
                - lang: 语言
                - use_gpu: 是否使用GPU
                
        Returns:
            bool: 初始化是否成劀
        """
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
        """
        加载表格检测和结构识别模型（PP-Structure！
        
        支持 PaddleOCR 3.x (PPStructureV3) 和旧版本 (PPStructure)
        
        Args:
            **kwargs: 模型配置参数
                - table_model_dir: 表格模型目录
                
        Returns:
            bool: 加载是否成功
        """
        if self._structure_initialized and self._structure_engine is not None:
            return True
        
        # 首先检查是否可以使生PPStructureV3 (PaddleOCR 3.x)
        ppstructure_v3_available = False
        try:
            from paddleocr import PPStructureV3
            ppstructure_v3_available = True
        except ImportError:
            pass
        
        if ppstructure_v3_available:
            # 使用 PPStructureV3 (PaddleOCR 3.x)
            try:
                from paddleocr import PPStructureV3
                import paddleocr
                
                # 记录 PaddleOCR 版本信息
                try:
                    paddleocr_version = getattr(paddleocr, '__version__', 'unknown')
                    self.logger.info(f"PaddleOCR version: {paddleocr_version}")
                except:
                    pass
                
                # 首先检柀PPStructureV3 的可用参敀
                import inspect
                try:
                    sig = inspect.signature(PPStructureV3.__init__)
                    self.logger.info(f"PPStructureV3.__init__ signature: {sig}")
                    # 获取所有参数名
                    param_names = list(sig.parameters.keys())
                    self.logger.info(f"PPStructureV3 available parameters: {param_names}")
                    
                    # 明确检查是否包后show_log（不应该有）
                    if 'show_log' in param_names:
                        self.logger.warning("PPStructureV3.__init__ contains 'show_log' parameter - this should not be used")
                except Exception as sig_error:
                    self.logger.debug(f"Could not inspect PPStructureV3 signature: {sig_error}")
                
                # PPStructureV3 的参数可能因版本而异，优先使用最小化配置以减少模型下轀
                # 禁用不必要的功能以加快初始化速度并减少内存占用（特别是Streamlit Cloud环境！
                init_success = False
                last_error = None
                
                # 尝试1: 最小化配置 - 只启用表格检测和识别，禁用所有其他功能
                # 这样可以避免下载不必要的模型（文档方向、文档矫正、公式识别、图表识别等！
                try:
                    self._structure_engine = PPStructureV3(
                        use_doc_orientation_classify=False,  # 禁用文档方向分类
                        use_doc_unwarping=False,  # 禁用文档矫正
                        use_textline_orientation=False,  # 禁用文本行方后
                        use_seal_recognition=False,  # 禁用印章识别
                        use_formula_recognition=False,  # 禁用公式识别（减少模型下载）
                        use_chart_recognition=False,  # 禁用图表识别
                        use_region_detection=False,  # 禁用区域检浀
                        use_table_recognition=True  # 只启用表格识别（这是我们需要的主要功能！
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
                
                # 尝试2: 简化配罀- 只禁用文档方向和矫正
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
                
                # 尝试3: 无参数（默认配置，会下载所有模型）
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
                
                # 尝试4: 使用 table_model_dir（如果提供）
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
                # 在3.x 版本中，PPStructure 不存在，所以不需要回退
                return False
        else:
            # 尝试旧版本的 PPStructure
            return self._load_legacy_ppstructure(kwargs)
    
    def _load_legacy_ppstructure(self, kwargs: Dict) -> bool:
        """
        加载旧版本的PPStructure模型
        
        Args:
            kwargs: 模型配置参数
                
        Returns:
            bool: 加载是否成功
        """
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
        """
        识别文本
        
        Args:
            image: PIL Image对象
            **kwargs: 其他参数
                - det: 是否进行文本检测（默认True！
                - rec: 是否进行文本识别（默认True！
                - cls: 是否进行角度分类（默认True！
                
        Returns:
            List[Dict]: OCR结果列表，每个元素包含：
                - text: 文本内容
                - bbox: 边界桀[[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                - confidence: 置信庀(0-1)
        """
        if not self._ocr_initialized:
            if not self.initialize():
                return []
        
        if self._ocr is None:
            self.logger.error("PaddleOCR OCR is not available")
            return []
        
        try:
            # 转换PIL Image为numpy array
            img_array = np.array(image)
            
            # 执行OCR
            det = kwargs.get('det', True)
            rec = kwargs.get('rec', True)
            cls = kwargs.get('cls', self.use_angle_cls)
            
            ocr_results = self._ocr.ocr(img_array, det=det, rec=rec, cls=cls)
            
            # 转换结果格式
            results = []
            if ocr_results and ocr_results[0]:
                for line in ocr_results[0]:
                    if line:
                        bbox_points = line[0]  # 四个角点坐标
                        text_info = line[1]    # (文本, 置信庀
                        
                        if text_info:
                            text = text_info[0]
                            confidence = text_info[1] if len(text_info) > 1 else 1.0
                            
                            # 转换bbox格式
                            x_coords = [point[0] for point in bbox_points]
                            y_coords = [point[1] for point in bbox_points]
                            x1, x2 = min(x_coords), max(x_coords)
                            y1, y2 = min(y_coords), max(y_coords)
                            
                            results.append({
                                'text': text,
                                'bbox': bbox_points,  # 保留原始角点格式
                                'bbox_rect': [x1, y1, x2, y2],  # 添加矩形格式
                                'confidence': float(confidence)
                            })
            
            return results
            
        except Exception as e:
            self.logger.error(f"PaddleOCR recognition failed: {e}")
            return []
    
    def detect_tables(self, image: Image.Image, **kwargs) -> List[Dict]:
        """
        检测表栀
        
        Args:
            image: PIL Image对象
            **kwargs: 其他参数（保留用于未来扩展）
                
        Returns:
            List[Dict]: 检测结果列表，每个元素包含！
                - bbox: 边界桀[x1, y1, x2, y2]
                - confidence: 置信庀(0-1)
                - type: 类型（如'table'！
        """
        if not self._structure_initialized:
            if not self.load_models():
                return []
        
        if self._structure_engine is None:
            self.logger.error("PaddleOCR PP-Structure is not available")
            return []
        
        try:
            # 转换PIL Image为numpy array
            img_array = np.array(image)
            
            # 根据版本使用不同的API
            if self._is_ppstructure_v3:
                # PPStructureV3 使用 predict() 方法，可以直接接又PIL Image 成numpy array
                # 优先使用 PIL Image，如果失败则尝试 numpy array
                try:
                    # 直接使用 PIL Image
                    results = self._structure_engine.predict(image)
                except (TypeError, AttributeError):
                    # 如果 PIL Image 不支持，转换一numpy array
                    # PPStructureV3 期望 BGR 格式的numpy array
                    import cv2
                    img_array = np.array(image)
                    # PIL Image 是RGB，需要转换为 BGR
                    if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    results = self._structure_engine.predict(img_array)
                
                # 转换 PPStructureV3 结果格式
                detection_results = []
                for result in results:
                    # PPStructureV3 返回的结果对象，需要提取表格信恀
                    # 结果可能包含多个元素，需要查找表格类垀
                    result_type = None
                    if hasattr(result, 'type'):
                        result_type = result.type
                    elif hasattr(result, 'get') and isinstance(result, dict):
                        result_type = result.get('type')
                    
                    if result_type == 'table':
                        # 提取边界框（PPStructureV3 的格式可能不同）
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
                                'raw': result  # 保留原始结果对象
                            })
                
                return detection_results
            else:
                # 旧版有PPStructure 使用 __call__ 方法
                # 注意：PPStructure的__call__方法不接受layout参数，直接传入图像数组即又
                structure_results = self._structure_engine(img_array)
                
                # 转换结果格式
                detection_results = []
                for item in structure_results:
                    if item.get('type') == 'table':
                        bbox = item.get('bbox', [])
                        if bbox and len(bbox) >= 4:
                            # bbox格式可能是[x1, y1, x2, y2]或[[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                            if isinstance(bbox[0], (list, tuple)):
                                # 角点格式，转换为矩形
                                x_coords = [point[0] for point in bbox]
                                y_coords = [point[1] for point in bbox]
                                x1, y1 = min(x_coords), min(y_coords)
                                x2, y2 = max(x_coords), max(y_coords)
                                bbox_rect = [x1, y1, x2, y2]
                            else:
                                # 已经是矩形格开
                                bbox_rect = bbox[:4]
                            
                            detection_results.append({
                                'bbox': bbox_rect,
                                'confidence': item.get('score', 1.0),
                                'type': 'table',
                                'raw': item  # 保留原始数据用于高级处理
                            })
                
                return detection_results
            
        except Exception as e:
            self.logger.error(f"PaddleOCR table detection failed: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return []
    
    def recognize_structure(self, image: Image.Image, table_bbox: Optional[List] = None, **kwargs) -> Dict:
        """
        识别表格结构
        
        Args:
            image: PIL Image对象（表格区域）
            table_bbox: 表格边界桀[x1, y1, x2, y2]（可选）
            **kwargs: 其他参数
                - return_raw: 是否返回原始输出（默认False！
                
        Returns:
            Dict: 结构识别结果，包含：
                - cells: 单元格列行
                - rows: 行信恀
                - columns: 列信恀
                - html: HTML格式的表格（如果可用！
                - 其他结构信息
        """
        if not self._structure_initialized:
            if not self.load_models():
                return {}
        
        if self._structure_engine is None:
            self.logger.error("PaddleOCR PP-Structure is not available")
            return {}
        
        try:
            # 如果指定了table_bbox，裁剪图僀
            if table_bbox:
                x1, y1, x2, y2 = table_bbox
                image = image.crop((x1, y1, x2, y2))
            
            # 根据版本使用不同的API
            if self._is_ppstructure_v3:
                # PPStructureV3 使用 predict() 方法，可以直接接又PIL Image 成numpy array
                try:
                    # 直接使用 PIL Image
                    results = self._structure_engine.predict(image)
                except (TypeError, AttributeError):
                    # 如果 PIL Image 不支持，转换一numpy array
                    # PPStructureV3 期望 BGR 格式的numpy array
                    import cv2
                    img_array = np.array(image)
                    # PIL Image 是RGB，需要转换为 BGR
                    if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    results = self._structure_engine.predict(img_array)
                
                # 查找表格结果
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
                
                # 转换 PPStructureV3 结果格式
                # PPStructureV3 的结果对象可能有不同的属怀
                html_content = ''
                if hasattr(table_result, 'html'):
                    html_content = table_result.html
                elif hasattr(table_result, 'get') and isinstance(table_result, dict):
                    html_content = table_result.get('html', '')
                
                # 尝试获取 markdown 内容
                markdown_content = ''
                if hasattr(table_result, 'markdown'):
                    markdown_content = table_result.markdown
                elif hasattr(table_result, 'save_to_markdown'):
                    # 如果支持 save_to_markdown，尝试获取内定
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
                        # 确保临时文件总是被清琀
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
                    'html': html_content or markdown_content,  # 使用 HTML 成markdown
                    'cells': cells,
                    'raw': table_result if kwargs.get('return_raw', False) else None
                }
                
                if markdown_content:
                    result['markdown'] = markdown_content
            else:
                # 旧版有PPStructure 使用 __call__ 方法
                # 转换PIL Image为numpy array
                img_array = np.array(image)
                
                # 执行结构识别
                structure_results = self._structure_engine(img_array)
                
                # 查找表格结果
                table_result = None
                for item in structure_results:
                    if item.get('type') == 'table':
                        table_result = item
                        break
                
                if not table_result:
                    self.logger.warning("No table structure found in image")
                    return {}
                
                # 转换结果格式
                result = {
                    'html': table_result.get('res', {}).get('html', ''),
                    'cells': table_result.get('res', {}).get('cells', []),
                    'raw': table_result if kwargs.get('return_raw', False) else None
                }
            
            # 尝试从HTML或cells中提取行列信恀
            if result.get('html'):
                # 可以进一步解析HTML获取行列信息
                result['has_structure'] = True
            elif result.get('cells'):
                # 从cells中提取行列信恀
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
        """
        识别指定区域的文有
        
        Args:
            image: PIL Image对象
            bbox: 区域边界桀[x1, y1, x2, y2]
            **kwargs: 其他参数
            
        Returns:
            List[Dict]: OCR结果列表，坐标已调整到原图坐标系
        """
        try:
            # 裁剪区域
            x1, y1, x2, y2 = bbox
            cropped = image.crop((x1, y1, x2, y2))
            
            # 识别文本
            results = self.recognize_text(cropped, **kwargs)
            
            # 调整bbox坐标到原图坐标系
            for result in results:
                if 'bbox' in result:
                    # 调整角点坐标
                    adjusted_bbox = []
                    for point in result['bbox']:
                        adjusted_bbox.append([point[0] + x1, point[1] + y1])
                    result['bbox'] = adjusted_bbox
                
                if 'bbox_rect' in result:
                    # 调整矩形坐标
                    rect = result['bbox_rect']
                    result['bbox_rect'] = [rect[0] + x1, rect[1] + y1, rect[2] + x1, rect[3] + y1]
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to recognize text in region: {e}")
            return []
    
    def is_available(self) -> bool:
        """
        检查引擎是否可生
        
        Returns:
            bool: 引擎是否可用
        """
        try:
            import paddleocr
            return True
        except ImportError:
            return False
