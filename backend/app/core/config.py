"""
DocuVision 配置文件
"""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        populate_by_name=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "DocuVision"
    APP_VERSION: str = "1.5.0"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Storage
    UPLOAD_DIR: str = "./uploads"
    OUTPUT_DIR: str = "./outputs"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB

    # OCR
    OCR_LANG: str = "ch"  # ch, en, multi

    # Phase 1 API - service-level configuration
    DEBUG_MODE: bool = Field(
        default=False,
        validation_alias=AliasChoices("APP_DEBUG_MODE", "DEBUG_MODE"),
    )
    DEBUG_OUTPUT_DIR: str = "./debug"
    DEBUG_KEEP_LAST_N: int = 50
    ENABLE_DEBUG_OVERLAYS: bool = Field(
        default=False,
        validation_alias=AliasChoices("APP_ENABLE_DEBUG_OVERLAYS", "ENABLE_DEBUG_OVERLAYS"),
    )
    USE_DOC_UNWARPING: bool = Field(
        default=False,
        validation_alias=AliasChoices("APP_USE_DOC_UNWARPING", "USE_DOC_UNWARPING"),
    )
    TABLE_ALLOW_FULLPAGE_FALLBACK: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "APP_TABLE_ALLOW_FULLPAGE_FALLBACK",
            "TABLE_ALLOW_FULLPAGE_FALLBACK",
        ),
    )
    LAYOUT_WORKER_INIT_TIMEOUT: int = Field(
        default=120,
        validation_alias=AliasChoices(
            "APP_LAYOUT_WORKER_INIT_TIMEOUT",
            "LAYOUT_WORKER_INIT_TIMEOUT",
        ),
    )

    # Webhook (HTTP delivery) — instance-level opt-in + admin auth
    WEBHOOK_ENABLED: bool = Field(
        default=False,
        validation_alias=AliasChoices("DOCUVISION_WEBHOOK_ENABLED", "WEBHOOK_ENABLED"),
    )
    WEBHOOK_ADMIN_TOKEN: str = Field(
        default="",
        validation_alias=AliasChoices("DOCUVISION_WEBHOOK_ADMIN_TOKEN", "WEBHOOK_ADMIN_TOKEN"),
    )

    # KIE (Qwen2.5-VL) — HuggingFace id or local directory
    KIE_QWEN_MODEL_ID: str = Field(
        default=os.path.expanduser(
            "~/.cache/modelscope/hub/models/Qwen/Qwen2___5-VL-3B-Instruct"
        ),
        validation_alias=AliasChoices(
            "DOCUVISION_KIE_QWEN_MODEL_ID",
            "KIE_QWEN_MODEL_ID",
        ),
    )
    KIE_QWEN_DEVICE_MAP: str = Field(
        default="auto",
        validation_alias=AliasChoices(
            "DOCUVISION_KIE_QWEN_DEVICE_MAP",
            "KIE_QWEN_DEVICE_MAP",
        ),
    )
    KIE_QWEN_TORCH_DTYPE: str = Field(
        default="bfloat16",
        validation_alias=AliasChoices(
            "DOCUVISION_KIE_QWEN_TORCH_DTYPE",
            "KIE_QWEN_TORCH_DTYPE",
        ),
    )
    KIE_MAX_PAGES: int = Field(
        default=5,
        validation_alias=AliasChoices("DOCUVISION_KIE_MAX_PAGES", "KIE_MAX_PAGES"),
    )
    BATCH_MAX_CONCURRENT_KIE: int = Field(
        default=1,
        validation_alias=AliasChoices(
            "DOCUVISION_BATCH_MAX_CONCURRENT_KIE",
            "BATCH_MAX_CONCURRENT_KIE",
        ),
    )
    KIE_WARMUP: bool = Field(
        default=False,
        validation_alias=AliasChoices("DOCUVISION_KIE_WARMUP", "KIE_WARMUP"),
    )

    # Queue persistence (Batch + HITL) — single SQLite file.
    # Path is relative to the backend cwd (i.e. ``backend/data/docuvision.sqlite``
    # on disk when run via ``python run.py`` from ``backend/``).
    SQLITE_DB_PATH: str = Field(
        default="data/docuvision.sqlite",
        validation_alias=AliasChoices("DOCUVISION_SQLITE_DB_PATH", "SQLITE_DB_PATH"),
    )


# 创建配置实例
settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.DEBUG_OUTPUT_DIR, exist_ok=True)
# Ensure the SQLite DB parent directory exists (queue persistence).
try:
    from pathlib import Path as _Path

    os.makedirs(_Path(settings.SQLITE_DB_PATH).parent, exist_ok=True)
except Exception:
    # Avoid crashing startup on misconfigured paths; the store will retry on init.
    pass

