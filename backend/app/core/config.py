"""
DocuVision 配置文件
"""

from pydantic_settings import BaseSettings
from pydantic import Field
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

    # ============================================
    # Phase 1 API - Service-Level Configuration
    # ============================================

    # Debug mode: when enabled, saves raw/fused/quality JSONs + images to backend/debug/{job_id}/
    # Must be service-level (not per-request) to prevent security issues and unnecessary disk I/O
    # env override: APP_DEBUG_MODE
    DEBUG_MODE: bool = Field(default=False, alias="APP_DEBUG_MODE")

    # Debug artifacts output directory
    DEBUG_OUTPUT_DIR: str = "./debug"

    # Maximum number of debug jobs to retain before cleanup (FIFO)
    DEBUG_KEEP_LAST_N: int = 50

    # Coordinate system strategy: if False, view layer applies inverse rotation to restore original image coords
    # If True, view layer uses preprocessed image coordinates directly
    # Must be service-level; all requests use the same strategy
    # env override: APP_USE_DOC_UNWARPING
    USE_DOC_UNWARPING: bool = Field(default=True, alias="APP_USE_DOC_UNWARPING")

    # OCR text fusion thresholds
    OCR_MIN_CONFIDENCE: float = 0.6  # min OCR text confidence to use for text replacement
    OCR_SUSPICIOUS_LENGTH_RATIO: float = 0.5  # if OCR text length differs by >50% from original, mark suspicious

    class Config:
        env_file = ".env"
        case_sensitive = True
        populate_by_name = True  # Allow both field name and alias


# 创建配置实例
settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.DEBUG_OUTPUT_DIR, exist_ok=True)

