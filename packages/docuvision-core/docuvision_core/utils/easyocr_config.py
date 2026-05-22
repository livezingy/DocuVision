# core/utils/easyocr_config.py
"""
EasyOCR配置工具
管理EasyOCR的本地模型路径，优先使用本地模型，如果不存在则自动下�?
"""
import os
import easyocr
from pathlib import Path
from typing import List, Optional
from docuvision_core.utils.logger import AppLogger
from docuvision_core.utils.path_utils import get_app_dir


class EasyOCRConfig:
    """EasyOCR配置管理�?""
    
    def __init__(self):
        self.logger = AppLogger.get_logger()
        self.base_dir = get_app_dir()
        self.model_dir = os.path.join(self.base_dir, 'models', 'EasyOCR', 'model')
        
        # 确保模型目录存在
        os.makedirs(self.model_dir, exist_ok=True)
        
        # 设置EasyOCR模型路径环境变量
        self._setup_model_path()
    
    def _setup_model_path(self):
        """设置EasyOCR模型路径环境变量"""
        try:
            # 设置EasyOCR模型下载路径
            os.environ['EASYOCR_MODULE_PATH'] = self.model_dir
            
            # 设置EasyOCR缓存路径
            cache_dir = os.path.join(self.model_dir, 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            os.environ['EASYOCR_CACHE_DIR'] = cache_dir
            
            self.logger.info(f"EasyOCR模型路径设置�? {self.model_dir}")
            
        except Exception as e:
            self.logger.error(f"设置EasyOCR模型路径失败: {str(e)}")
    
    def get_reader(self, languages: List[str] = ['en'], gpu: bool = False, 
                   model_storage_directory: Optional[str] = None, 
                   download_enabled: bool = True) -> easyocr.Reader:
        """
        获取EasyOCR Reader实例，优先使用本地模�?
        
        Args:
            languages: 支持的语言列表
            gpu: 是否使用GPU
            model_storage_directory: 模型存储目录（如果为None则使用默认目录）
            download_enabled: 是否允许下载模型（如果本地没有）
            
        Returns:
            EasyOCR Reader实例
        """
        try:
            # 使用配置的模型目�?
            if model_storage_directory is None:
                model_storage_directory = self.model_dir
            
            # 检查本地模型是否存�?
            local_models_exist = self._check_local_models(languages)
            
            if local_models_exist:
                self.logger.info(f"使用本地EasyOCR模型: {model_storage_directory}")
                download_enabled = False  # 本地有模型，不需要下�?
            else:
                self.logger.info("本地EasyOCR模型不存在，将自动下�?)
                download_enabled = True
            
            # 创建Reader实例
            reader = easyocr.Reader(
                languages,
                gpu=gpu,
                model_storage_directory=model_storage_directory,
                download_enabled=download_enabled
            )
            
            self.logger.info(f"EasyOCR Reader初始化成功，语言: {languages}, GPU: {gpu}")
            return reader
            
        except Exception as e:
            self.logger.error(f"EasyOCR Reader初始化失�? {str(e)}")
            # 如果初始化失败，尝试使用默认配置
            try:
                self.logger.warning("尝试使用默认EasyOCR配置")
                return easyocr.Reader(languages, gpu=gpu, download_enabled=True)
            except Exception as fallback_error:
                self.logger.error(f"EasyOCR默认配置也失�? {str(fallback_error)}")
                raise fallback_error
    
    def _check_local_models(self, languages: List[str]) -> bool:
        """
        检查本地模型是否存�?
        
        Args:
            languages: 语言列表
            
        Returns:
            如果所有需要的模型都存在则返回True
        """
        try:
            # 检查CRAFT模型（文本检测）
            craft_model = os.path.join(self.model_dir, 'craft_mlt_25k.pth')
            if not os.path.exists(craft_model):
                self.logger.debug("CRAFT模型不存�?)
                return False
            
            # 检查识别模�?
            for lang in languages:
                if lang == 'en':
                    recog_model = os.path.join(self.model_dir, 'english_g2.pth')
                else:
                    # 其他语言的模型文件命名规�?
                    recog_model = os.path.join(self.model_dir, f'{lang}_g2.pth')
                
                if not os.path.exists(recog_model):
                    self.logger.debug(f"识别模型不存�? {recog_model}")
                    return False
            
            self.logger.debug("所有需要的EasyOCR模型都存�?)
            return True
            
        except Exception as e:
            self.logger.error(f"检查本地模型失�? {str(e)}")
            return False
    
    def download_models(self, languages: List[str] = ['en']) -> bool:
        """
        手动下载EasyOCR模型
        
        Args:
            languages: 需要下载的语言列表
            
        Returns:
            下载是否成功
        """
        try:
            self.logger.info(f"开始下载EasyOCR模型，语言: {languages}")
            
            # 创建临时Reader来触发模型下�?
            reader = easyocr.Reader(
                languages,
                model_storage_directory=self.model_dir,
                download_enabled=True
            )
            
            # 测试Reader是否工作正常
            import numpy as np
            test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
            _ = reader.readtext(test_image)
            
            self.logger.info("EasyOCR模型下载并测试成�?)
            return True
            
        except Exception as e:
            self.logger.error(f"EasyOCR模型下载失败: {str(e)}")
            return False
    
    def get_model_info(self) -> dict:
        """
        获取模型信息
        
        Returns:
            包含模型路径和存在状态的字典
        """
        try:
            model_info = {
                'model_directory': self.model_dir,
                'craft_model': {
                    'path': os.path.join(self.model_dir, 'craft_mlt_25k.pth'),
                    'exists': os.path.exists(os.path.join(self.model_dir, 'craft_mlt_25k.pth'))
                },
                'recognition_models': {}
            }
            
            # 检查各种语言的识别模�?
            languages = ['en', 'ch_sim', 'ch_tra', 'ja', 'ko', 'th', 'vi', 'ar', 'hi']
            for lang in languages:
                if lang == 'en':
                    model_path = os.path.join(self.model_dir, 'english_g2.pth')
                else:
                    model_path = os.path.join(self.model_dir, f'{lang}_g2.pth')
                
                model_info['recognition_models'][lang] = {
                    'path': model_path,
                    'exists': os.path.exists(model_path)
                }
            
            return model_info
            
        except Exception as e:
            self.logger.error(f"获取模型信息失败: {str(e)}")
            return {'error': str(e)}


# 全局配置实例
_easyocr_config = None

def get_easyocr_config() -> EasyOCRConfig:
    """获取全局EasyOCR配置实例"""
    global _easyocr_config
    if _easyocr_config is None:
        _easyocr_config = EasyOCRConfig()
    return _easyocr_config

def get_easyocr_reader(languages: List[str] = ['en'], gpu: bool = False) -> easyocr.Reader:
    """
    便捷函数：获取配置好的EasyOCR Reader
    
    Args:
        languages: 支持的语言列表
        gpu: 是否使用GPU
        
    Returns:
        EasyOCR Reader实例
    """
    config = get_easyocr_config()
    return config.get_reader(languages, gpu)
