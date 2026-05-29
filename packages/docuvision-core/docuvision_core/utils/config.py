# core/utils/config.py
import json
import os
import threading
from typing import Any, Dict

from docuvision_core.utils.model_paths import (
    table_transformer_detection_dir,
    table_transformer_structure_dir,
)
from docuvision_core.utils.path_utils import get_app_dir, resolve_tesseract_cmd


class Config:
    """Configuration manager for table parser and UI defaults."""

    _instance = None
    _lock = threading.Lock()

    DEFAULT_CONFIG = {
        "ui": {
            "theme": "light",
            "output_path": "",
            "export_format": "csv",
            "pages": "all",
            "table_method": "camelot",
            "table_score_threshold": 0.6,
            "table_iou_threshold": 0.3,
            "transformer_detection_threshold": 0.5,
            "transformer_structure_threshold": 0.5,
            "tesseract_threshold": 0.5,
            "transformer_preprocess": True,
        },
        "table_models": {
            "detection_confidence": 0.5,
            "structure_confidence": 0.5,
            "ocr_confidence": 0.5,
            "detection_model_path": "models/table-transformer/detection",
            "structure_model_path": "models/table-transformer/structure",
            "ocr_model_path": "models/Tesseract-OCR/tesseract.exe",
            "max_image_size": 1024,
            "device": "cpu",
        },
        "table_parser": {
            "structure_border_width": 5,
            "structure_preprocess": True,
            "structure_expand_rowcol": 1,
            "cell_ocr_enabled": True,
            "table_ocr_engine": "easyocr",
            "table_ocr_languages": ["eng"],
        },
        "table_evaluator": {
            "domain_matrix": {
                "financial": [1.3, 0.9, 1.4, 0.8],
                "scientific": [1.1, 1.0, 1.5, 0.7],
                "medical": [0.9, 0.8, 1.8, 0.9],
                "unstructured": [1.0, 1.0, 1.0, 1.0],
            },
            "base_weights": {
                "structural": 0.35,
                "layout": 0.30,
                "content": 0.20,
                "functional": 0.15,
            },
            "sub_weights": {
                "financial": 0.5,
                "scientific": 0.5,
                "medical": 0.5,
                "unstructured": 0.5,
            },
        },
    }

    def __new__(cls, config_file: str = "config.json"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_file: str = None):
        if getattr(self, "_initialized", False):
            return

        base_dir = get_app_dir()
        if config_file is None:
            config_file = os.path.join(base_dir, "config", "config.json")

        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        self.DEFAULT_CONFIG["table_models"]["detection_model_path"] = str(
            table_transformer_detection_dir()
        )
        self.DEFAULT_CONFIG["table_models"]["structure_model_path"] = str(
            table_transformer_structure_dir()
        )
        self.DEFAULT_CONFIG["table_models"]["ocr_model_path"] = resolve_tesseract_cmd()

        self.load()
        self._initialized = True

    def load(self) -> None:
        """Load configuration from file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception:
                self.config = {}
        else:
            self.config = self.DEFAULT_CONFIG.copy()

    def save(self) -> None:
        """Persist UI settings to disk."""
        try:
            save_dict = {"ui": self.config.get("ui", self.DEFAULT_CONFIG["ui"])}
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(save_dict, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        """Return a config value, falling back to defaults."""
        return self.config.get(key, self.DEFAULT_CONFIG.get(key, default))

    def set(self, key: str, value: Any) -> None:
        """Set a config value and persist UI settings when needed."""
        self.config[key] = value
        if key == "ui":
            self.save()

    def get_all(self) -> Dict[str, Any]:
        """Merge defaults with loaded overrides."""
        merged = self.DEFAULT_CONFIG.copy()
        merged.update(self.config)
        return merged


def load_config(config_file: str = None) -> Dict[str, Any]:
    """Load application configuration as a plain dict."""
    config_manager = Config(config_file)
    return config_manager.get_all()
