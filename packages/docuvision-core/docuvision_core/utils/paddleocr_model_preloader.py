# core/utils/paddleocr_model_preloader.py
"""
PaddleOCR模型预加载工�?

在应用启动时预下载PaddleOCR模型，避免在用户使用时下载导致超�?
"""

import os
import threading
from typing import Optional
from docuvision_core.utils.logger import AppLogger


class PaddleOCRModelPreloader:
    """PaddleOCR模型预加载器"""
    
    _instance: Optional['PaddleOCRModelPreloader'] = None
    _lock = threading.Lock()
    _preload_started = False
    _preload_completed = False
    _preload_error: Optional[Exception] = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.logger = AppLogger.get_logger()
        return cls._instance
    
    def preload_models(self, background: bool = True) -> bool:
        """
        预加载PaddleOCR模型
        
        Args:
            background: 是否在后台线程中加载（默认True，避免阻塞应用启动）
            
        Returns:
            bool: 是否成功启动预加载（不表示加载完成）
        """
        if self._preload_started:
            self.logger.info("PaddleOCR模型预加载已启动，跳过重复启�?)
            return True
        
        with self._lock:
            if self._preload_started:
                return True
            
            self._preload_started = True
            
            if background:
                # 在后台线程中预加�?
                thread = threading.Thread(
                    target=self._preload_models_worker,
                    daemon=True,
                    name="PaddleOCRModelPreloader"
                )
                thread.start()
                self.logger.info("PaddleOCR模型预加载已在后台启�?)
                return True
            else:
                # 同步预加�?
                return self._preload_models_worker()
    
    def _preload_models_worker(self) -> bool:
        """预加载模型的工作函数"""
        try:
            self.logger.info("开始预加载PaddleOCR模型...")
            
            # 检查是否可以使用PPStructureV3
            try:
                from paddleocr import PPStructureV3
                ppstructure_v3_available = True
            except ImportError:
                self.logger.info("PPStructureV3不可用，跳过预加�?)
                self._preload_completed = True
                return True
            
            if not ppstructure_v3_available:
                self._preload_completed = True
                return True
            
            # 使用最小化配置预加载模�?
            # 只启用表格识别，禁用其他功能以减少模型下�?
            try:
                self.logger.info("正在初始化PPStructureV3（最小化配置）以预下载模�?..")
                structure_engine = PPStructureV3(
                    use_doc_orientation_classify=False,  # 禁用文档方向分类
                    use_doc_unwarping=False,  # 禁用文档矫正
                    use_textline_orientation=False,  # 禁用文本行方�?
                    use_seal_recognition=False,  # 禁用印章识别
                    use_formula_recognition=False,  # 禁用公式识别
                    use_chart_recognition=False,  # 禁用图表识别
                    use_region_detection=False,  # 禁用区域检�?
                    use_table_recognition=True  # 只启用表格识�?
                )
                self.logger.info("�?PaddleOCR模型预加载完�?)
                self._preload_completed = True
                return True
                
            except Exception as e:
                error_msg = str(e)
                # 检查是否是依赖错误
                if "DependencyError" in error_msg or "paddlex" in error_msg.lower():
                    self.logger.warning(f"PaddleOCR依赖错误，跳过预加载: {e}")
                    self._preload_completed = True
                    return False
                else:
                    self.logger.error(f"PaddleOCR模型预加载失�? {e}")
                    self._preload_error = e
                    self._preload_completed = True
                    return False
                    
        except Exception as e:
            self.logger.error(f"PaddleOCR模型预加载过程中发生错误: {e}")
            self._preload_error = e
            self._preload_completed = True
            return False
    
    def is_preload_completed(self) -> bool:
        """检查预加载是否完成"""
        return self._preload_completed
    
    def get_preload_error(self) -> Optional[Exception]:
        """获取预加载错误（如果有）"""
        return self._preload_error
    
    def check_models_exist(self) -> bool:
        """
        检查模型文件是否已存在
        
        Returns:
            bool: 模型文件是否存在
        """
        try:
            # PaddleX模型通常保存�?~/.paddlex/official_models/ 目录�?
            # 在Streamlit Cloud中，路径�?/home/appuser/.paddlex/official_models/
            home_dir = os.path.expanduser("~")
            paddlex_models_dir = os.path.join(home_dir, ".paddlex", "official_models")
            
            if not os.path.exists(paddlex_models_dir):
                self.logger.info(f"PaddleOCR模型目录不存�? {paddlex_models_dir}")
                return False
            
            # 检查一些关键模型目录是否存�?
            # 表格相关的核心模型（最小化配置需要的模型�?
            table_models = [
                "PP-LCNet_x1_0_table_cls",  # 表格分类
                "SLANeXt_wired",  # 有线表格结构识别
                "SLANet_plus",  # 无线表格结构识别
                "RT-DETR-L_wired_table_cell_det",  # 有线表格单元格检�?
                "RT-DETR-L_wireless_table_cell_det",  # 无线表格单元格检�?
            ]
            
            # OCR相关的核心模�?
            ocr_models = [
                "PP-OCRv5_server_det",  # 文本检�?
                "PP-OCRv5_server_rec",  # 文本识别
            ]
            
            # 布局相关的核心模�?
            layout_models = [
                "PP-DocBlockLayout",  # 文档块布局
                "PP-DocLayout_plus-L",  # 文档布局增强
            ]
            
            all_models = table_models + ocr_models + layout_models
            
            # 检查至少有一些模型存�?
            existing_models = []
            for model_name in all_models:
                model_dir = os.path.join(paddlex_models_dir, model_name)
                if os.path.exists(model_dir):
                    # 进一步检查模型目录中是否有文�?
                    if os.path.isdir(model_dir) and os.listdir(model_dir):
                        existing_models.append(model_name)
            
            # 至少需要表格相关的核心模型和OCR模型
            required_table_models = ["PP-LCNet_x1_0_table_cls", "SLANeXt_wired", "SLANet_plus"]
            required_ocr_models = ["PP-OCRv5_server_det", "PP-OCRv5_server_rec"]
            
            has_table_models = any(m in existing_models for m in required_table_models)
            has_ocr_models = any(m in existing_models for m in required_ocr_models)
            
            if has_table_models and has_ocr_models and len(existing_models) >= 5:
                self.logger.info(f"�?检测到已存在的PaddleOCR模型: {len(existing_models)}个核心模�?)
                return True
            else:
                self.logger.info(f"⚠️ 检测到部分PaddleOCR模型: {len(existing_models)}个，需要预加载")
                self.logger.info(f"   表格模型: {has_table_models}, OCR模型: {has_ocr_models}")
                return False
                
        except Exception as e:
            self.logger.warning(f"检查模型文件时出错: {e}")
            return False


def preload_paddleocr_models(background: bool = True) -> bool:
    """
    预加载PaddleOCR模型的便捷函�?
    
    Args:
        background: 是否在后台线程中加载
        
    Returns:
        bool: 是否成功启动预加�?
    """
    preloader = PaddleOCRModelPreloader()
    return preloader.preload_models(background=background)


def check_paddleocr_models_exist() -> bool:
    """
    检查PaddleOCR模型是否已存在的便捷函数
    
    Returns:
        bool: 模型是否存在
    """
    preloader = PaddleOCRModelPreloader()
    return preloader.check_models_exist()
