"""KIE Qwen local model path resolution (no GPU)."""

import os
import sys

import pytest

from app.services import kie_qwen_service as kie_qwen
from app.services.kie_qwen_service import (
    _configured_kie_model_id,
    _discover_local_kie_model_dir,
    _is_hub_model_id,
    _resolve_kie_model_path,
    preflight_kie_model_path,
)


def _touch_config(model_dir):
    (model_dir / "config.json").write_text("{}", encoding="utf-8")


def _pin_ready(monkeypatch, model_dir) -> None:
    """Make "model ready" mean exactly ``model_dir`` (and nothing else).

    ``_resolve_kie_model_path`` returns the configured path as soon as it looks
    ready (kie_qwen_service.py:131) and only then remaps /root -> ~ (:134).
    On a cloud GPU box the real ``/root/.cache/modelscope/...`` model IS ready,
    so that first branch wins and the assertions below can never observe the
    remap or the discovery fallback. Pinning the readiness predicate keeps the
    test hermetic on both a bare CI box and a fully populated GPU host.
    """
    target = os.path.realpath(str(model_dir))

    def _ready(path: str) -> bool:
        return os.path.realpath(str(path)) == target

    monkeypatch.setattr(kie_qwen, "_local_kie_model_ready", _ready)


def test_is_hub_model_id():
    assert _is_hub_model_id("Qwen/Qwen2.5-VL-3B-Instruct") is True
    assert _is_hub_model_id("/root/.cache/modelscope/hub/models/Qwen/x") is False
    assert _is_hub_model_id("~/.cache/foo") is False


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="asserts $HOME-driven expansion; os.path.expanduser ignores $HOME on Windows",
)
def test_resolve_kie_model_path_expands_tilde(tmp_path, monkeypatch):
    model_dir = tmp_path / ".cache" / "modelscope" / "hub" / "models" / "Qwen" / "Qwen2___5-VL-3B-Instruct"
    model_dir.mkdir(parents=True)
    _touch_config(model_dir)
    monkeypatch.setenv("HOME", str(tmp_path))
    resolved = _resolve_kie_model_path("~/.cache/modelscope/hub/models/Qwen/Qwen2___5-VL-3B-Instruct")
    assert resolved == str(model_dir)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="asserts the /root -> $HOME remap; os.path.expanduser ignores $HOME on Windows",
)
def test_resolve_kie_model_path_remaps_root_to_home(tmp_path, monkeypatch):
    model_dir = tmp_path / ".cache" / "modelscope" / "hub" / "models" / "Qwen" / "Qwen2___5-VL-3B-Instruct"
    model_dir.mkdir(parents=True)
    _touch_config(model_dir)
    monkeypatch.setenv("HOME", str(tmp_path))
    _pin_ready(monkeypatch, model_dir)
    root_path = "/root/.cache/modelscope/hub/models/Qwen/Qwen2___5-VL-3B-Instruct"
    resolved = _resolve_kie_model_path(root_path)
    assert resolved == str(model_dir)


def test_discover_via_modelscope_cache_env(tmp_path, monkeypatch):
    cache_root = tmp_path / "ms_cache"
    model_dir = cache_root / "hub" / "models" / "Qwen" / "Qwen2___5-VL-3B-Instruct"
    model_dir.mkdir(parents=True)
    _touch_config(model_dir)
    monkeypatch.setenv("MODELSCOPE_CACHE", str(cache_root))
    monkeypatch.setenv("HOME", str(tmp_path / "empty_home"))
    _pin_ready(monkeypatch, model_dir)
    discovered = _discover_local_kie_model_dir()
    assert discovered == str(model_dir)
    resolved = _resolve_kie_model_path("/root/.cache/modelscope/hub/models/Qwen/Qwen2___5-VL-3B-Instruct")
    assert resolved == str(model_dir)


def test_configured_kie_model_id_prefers_env(monkeypatch):
    monkeypatch.setenv("KIE_QWEN_MODEL_ID", "/env/kie-model")
    monkeypatch.delenv("DOCUVISION_KIE_QWEN_MODEL_ID", raising=False)
    assert _configured_kie_model_id() == "/env/kie-model"


def test_preflight_hub_id():
    pf = preflight_kie_model_path("Qwen/Qwen2.5-VL-3B-Instruct")
    assert pf["is_hub_id"] is True
    assert pf["resolved"] == "Qwen/Qwen2.5-VL-3B-Instruct"
