"""Settings env aliases for KIE model path + PaddleX cache home (pydantic-settings v2).

Bridge tests call ``_bridge_paddle_pdx_cache_home`` directly instead of reloading
``app.core.config``: reloading would swap the ``settings`` singleton and split
identity with modules that did ``from app.core.config import settings`` at import
time (measured 2026-11-20: reload here broke test_route_doc_reconciliation).
"""

import os

from app.core.config import Settings, _bridge_paddle_pdx_cache_home


def test_settings_reads_docuvision_kie_model_id(monkeypatch):
    monkeypatch.setenv(
        "DOCUVISION_KIE_QWEN_MODEL_ID",
        "/home/aistudio/.cache/modelscope/hub/models/Qwen/Qwen2___5-VL-3B-Instruct",
    )
    settings = Settings()
    assert settings.KIE_QWEN_MODEL_ID == (
        "/home/aistudio/.cache/modelscope/hub/models/Qwen/Qwen2___5-VL-3B-Instruct"
    )


def test_settings_reads_paddle_pdx_cache_home_alias(monkeypatch):
    monkeypatch.setenv(
        "DOCUVISION_PADDLE_PDX_CACHE_HOME", "/home/aistudio/work/paddlex_cache"
    )
    assert Settings().PADDLE_PDX_CACHE_HOME == "/home/aistudio/work/paddlex_cache"


def test_paddle_pdx_cache_home_default_empty(monkeypatch):
    monkeypatch.delenv("PADDLE_PDX_CACHE_HOME", raising=False)
    monkeypatch.delenv("DOCUVISION_PADDLE_PDX_CACHE_HOME", raising=False)
    assert Settings().PADDLE_PDX_CACHE_HOME == ""


def test_bridge_exports_paddle_pdx_cache_home(monkeypatch):
    monkeypatch.delenv("PADDLE_PDX_CACHE_HOME", raising=False)
    _bridge_paddle_pdx_cache_home("/tmp/pdx-root")
    try:
        assert os.environ.get("PADDLE_PDX_CACHE_HOME") == "/tmp/pdx-root"
    finally:
        monkeypatch.delenv("PADDLE_PDX_CACHE_HOME", raising=False)


def test_bridge_expands_user_home(monkeypatch):
    monkeypatch.delenv("PADDLE_PDX_CACHE_HOME", raising=False)
    _bridge_paddle_pdx_cache_home("~/pdx-cache")
    try:
        assert os.environ["PADDLE_PDX_CACHE_HOME"] == os.path.expanduser("~/pdx-cache")
    finally:
        monkeypatch.delenv("PADDLE_PDX_CACHE_HOME", raising=False)


def test_bridge_keeps_shell_env_priority(monkeypatch):
    monkeypatch.setenv("PADDLE_PDX_CACHE_HOME", "/from/shell")
    _bridge_paddle_pdx_cache_home("/from/dotenv")
    assert os.environ.get("PADDLE_PDX_CACHE_HOME") == "/from/shell"


def test_bridge_ignores_empty_setting(monkeypatch):
    monkeypatch.delenv("PADDLE_PDX_CACHE_HOME", raising=False)
    _bridge_paddle_pdx_cache_home("")
    assert "PADDLE_PDX_CACHE_HOME" not in os.environ
