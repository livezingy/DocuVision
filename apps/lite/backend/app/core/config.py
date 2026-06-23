"""DocuVision Lite configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class LiteSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DEBUG: bool = False

    MAX_FILE_SIZE_MB: int = 50
    MAX_PAGES: int = 50
    SYNC_MAX_PAGES: int = 10
    JOB_TTL_HOURS: int = 24

    CORS_ORIGINS: str = "http://localhost:8001,http://127.0.0.1:8001,http://localhost:8501"

    JOB_DATA_DIR: str = "data/lite_jobs"

    PREVIEW_DATA_DIR: str = "data/lite_previews"

    # Raster (image / scan PDF) Table Transformer extraction; default off in Lite.
    RASTER_TABLE_EXTRACTION_ENABLED: bool = False

    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    DEMO_VALIDATION_DIR: str = "data/demo_validation"


settings = LiteSettings()
