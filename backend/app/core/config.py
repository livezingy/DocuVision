"""
DocuVision 配置文件
"""

from pydantic_settings import BaseSettings
from pydantic import Field
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

    # Debug overlay images: when enabled, renders bounding-box overlays on source images at each pipeline stage.
    # Disabled by default to avoid unnecessary disk I/O on production deployments.
    # env override: APP_ENABLE_DEBUG_OVERLAYS
    ENABLE_DEBUG_OVERLAYS: bool = Field(default=False, alias="APP_ENABLE_DEBUG_OVERLAYS")

    # Coordinate system strategy: keep UVDoc unwarping disabled by default.
    # This preserves PP-StructureV3 text spacing and keeps view coordinates in original image space.
    # env override: APP_USE_DOC_UNWARPING
    USE_DOC_UNWARPING: bool = Field(default=False, alias="APP_USE_DOC_UNWARPING")

    # Table strategy: when False, table service only consumes table regions from layout output.
    # This avoids duplicated full-page PPStructure inference by default.
    # env override: APP_TABLE_ALLOW_FULLPAGE_FALLBACK
    TABLE_ALLOW_FULLPAGE_FALLBACK: bool = Field(default=False, alias="APP_TABLE_ALLOW_FULLPAGE_FALLBACK")

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

