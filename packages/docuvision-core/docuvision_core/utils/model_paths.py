"""Unified model storage paths under the docuvision-core package root."""

from __future__ import annotations

import os
from pathlib import Path

from docuvision_core.utils.path_utils import get_app_dir

MODELS_ROOT_ENV = "DOCUVISION_MODELS_DIR"
OFFLINE_ENV = "DOCUVISION_OFFLINE"


def is_offline_mode() -> bool:
    """Return True when network model downloads must be disabled."""
    return os.environ.get(OFFLINE_ENV, "").strip().lower() in {"1", "true", "yes"}


def get_models_root() -> Path:
    """Return the root directory for all Lite/core ML model weights."""
    override = os.environ.get(MODELS_ROOT_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(get_app_dir()) / "models"


def table_transformer_detection_dir() -> Path:
    return get_models_root() / "table-transformer" / "detection"


def table_transformer_structure_dir() -> Path:
    return get_models_root() / "table-transformer" / "structure"


def easyocr_model_dir() -> Path:
    return get_models_root() / "EasyOCR" / "model"


def local_model_ready(model_dir: Path) -> bool:
    """Return True when a Hugging Face-style local model directory is usable."""
    return (model_dir / "config.json").is_file()
