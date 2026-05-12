"""PaddleX 3.x 在旧版 ``aistudio-sdk`` 环境下的 ``snapshot_download`` 兼容层。

**背景**：部分环境固定 ``aistudio-sdk==0.2.x``，仅提供 ``aistudio_sdk.hub.download``，
而 PaddleX 期望 ``aistudio_sdk.snapshot_download``。在 **任何** ``import paddlex`` 之前
调用本模块，可向 ``sys.modules`` 注册合成子模块，将 ``snapshot_download`` 指向 ``hub.download``。

必须在 ``app.main`` 中 ``import paddlex`` 之前调用（见 ``main.py``）。
"""

from __future__ import annotations

import importlib
import sys
import types


def install_aistudio_snapshot_shim_for_paddlex() -> bool:
    """若仅有旧版 ``aistudio-sdk``（无 ``snapshot_download`` 子模块），则注册兼容 shim。

    Returns:
        True 表示已安装 shim；False 表示已有原生 ``snapshot_download`` 或无法从 ``hub`` 取 ``download``。
    """
    mod_name = "aistudio_sdk.snapshot_download"
    if mod_name in sys.modules:
        return False
    try:
        importlib.import_module(mod_name)
        return False
    except (ModuleNotFoundError, ImportError):
        pass
    try:
        from aistudio_sdk.hub import download as _hub_download  # type: ignore
    except ImportError:
        return False

    shim = types.ModuleType(mod_name)
    shim.snapshot_download = _hub_download  # type: ignore[attr-defined]
    sys.modules[mod_name] = shim
    try:
        import aistudio_sdk  # type: ignore

        setattr(aistudio_sdk, "snapshot_download", shim)
    except ImportError:
        pass
    return True
