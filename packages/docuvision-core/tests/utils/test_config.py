"""Regression tests for config module syntax and load behavior."""

from __future__ import annotations

import importlib


def test_config_module_imports_and_loads_defaults() -> None:
    config_mod = importlib.import_module("docuvision_core.utils.config")
    cfg = config_mod.load_config()
    assert "table_models" in cfg
    assert "table_parser" in cfg
    assert cfg["table_models"]["device"] == "cpu"
