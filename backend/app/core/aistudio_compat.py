"""PaddleX 与 PaddleNLP 共用环境下的 ``aistudio-sdk`` 兼容层。

**背景**（见 PaddleNLP #10781、#11186）：

- ``aistudio-sdk>=0.3``：提供 ``aistudio_sdk.snapshot_download``，PaddleX 3.3.x 依赖该入口。
- ``aistudio-sdk<0.3``（如 0.2.6）：提供 ``aistudio_sdk.hub.download``，PaddleNLP / Taskflow 依赖该入口。

二者在同一 venv 中无法仅靠升/降级同时满足。DocuVision 采用 **方案 A**：

- 固定 ``aistudio-sdk==0.2.6`` 以满足 PaddleNLP。
- 在 **任何** ``import paddlex`` 之前调用本模块，向 ``sys.modules`` 注册合成子模块
  ``aistudio_sdk.snapshot_download``，将 ``snapshot_download`` 指向 ``hub.download``，
  使 PaddleX 的 ``from aistudio_sdk.snapshot_download import snapshot_download`` 仍能工作。

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
