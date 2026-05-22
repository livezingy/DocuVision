# core/utils/config.py
import json
import os
from typing import Any, Dict, Optional
import threading
from docuvision_core.utils.path_utils import get_app_dir

class Config:
"""config module."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                # Comment.
                self.config = {}
        else:
            self.config = self.DEFAULT_CONFIG.copy()
            

    def save(self) -> None:
        """Docstring."""
        try:
            # Comment.
            save_dict = {"ui": self.config.get("ui", self.DEFAULT_CONFIG["ui"])}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(save_dict, f, indent=4, ensure_ascii=False)
        except Exception as e:
            # Comment.
            pass


    def get(self, key: str, default: Any = None) -> Any:
        """Docstring."""
        # Comment.
        return self.config.get(key, self.DEFAULT_CONFIG.get(key, default))

    def set(self, key: str, value: Any) -> None:
        """Docstring."""
        self.config[key] = value
        if key == "ui":
            self.save()

    def get_all(self) -> Dict[str, Any]:
        """Docstring."""
        merged = self.DEFAULT_CONFIG.copy()
        merged.update(self.config)
        return merged


def load_config(config_file: str = None) -> Dict[str, Any]:
    """Docstring."""
    config_manager = Config(config_file)
    return config_manager.get_all()