"""Tests for unified model path resolution."""

import os
from pathlib import Path

import pytest

from docuvision_core.utils.model_paths import (
    easyocr_model_dir,
    get_models_root,
    is_offline_mode,
    local_model_ready,
    table_transformer_detection_dir,
    table_transformer_structure_dir,
)
from docuvision_core.utils.path_utils import get_app_dir


def test_get_models_root_default_under_app_dir():
    root = get_models_root()
    assert root == Path(get_app_dir()) / "models"


def test_get_models_root_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("DOCUVISION_MODELS_DIR", str(tmp_path / "shared-models"))
    assert get_models_root() == (tmp_path / "shared-models").resolve()


def test_table_transformer_subdirs():
    root = get_models_root()
    assert table_transformer_detection_dir() == root / "table-transformer" / "detection"
    assert table_transformer_structure_dir() == root / "table-transformer" / "structure"


def test_easyocr_model_dir():
    assert easyocr_model_dir() == get_models_root() / "EasyOCR" / "model"


def test_local_model_ready_requires_config_json(tmp_path):
    model_dir = tmp_path / "det"
    model_dir.mkdir()
    assert not local_model_ready(model_dir)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    assert local_model_ready(model_dir)


@pytest.mark.parametrize("value", ["1", "true", "YES"])
def test_is_offline_mode_truthy(monkeypatch, value):
    monkeypatch.setenv("DOCUVISION_OFFLINE", value)
    assert is_offline_mode()


def test_is_offline_mode_default_false(monkeypatch):
    monkeypatch.delenv("DOCUVISION_OFFLINE", raising=False)
    assert not is_offline_mode()
