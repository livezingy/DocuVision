"""
DocuVision 配置文件
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """应用配置"""

    # 应用基础配置
    APP_NAME: str = "DocuVision"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 文件存储配置
    UPLOAD_DIR: str = "./uploads"
    OUTPUT_DIR: str = "./outputs"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB

    # OCR 配置
    OCR_LANG: str = "ch"  # ch, en, multi
    OCR_USE_GPU: bool = False
    OCR_MODEL_DIR: Optional[str] = None

    # 版面分析配置
    LAYOUT_MODEL: str = "ppstructure"  # ppstructure, layoutparser
    LAYOUT_RECOVERY: bool = True

    # 表格识别配置
    TABLE_MODEL: str = "ppstructure"
    TABLE_MAX_LEN: int = 488

    # Redis 配置 (用于任务队列)
    REDIS_URL: str = "redis://localhost:6379/0"

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./docuvision.db"

    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建配置实例
settings = Settings()

# 确保目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

