"""Prepend pip-shipped NVIDIA / PyTorch libs to LD_LIBRARY_PATH (Pro GPU)."""

from __future__ import annotations

import os
import site
import sys

_LIB_SUBDIRS = (
    "nvidia/cusparselt/lib",
    "nvidia/cusparse/lib",
    "nvidia/cublas/lib",
    "nvidia/cuda_runtime/lib",
    "nvidia/nvjitlink/lib",
    "nvidia/cudnn/lib",
    "nvidia/cufft/lib",
    "nvidia/cusolver/lib",
    "nvidia/nccl/lib",
    "nvidia/nvtx/lib",
    "torch/lib",
)


def _site_roots() -> list[str]:
    roots: list[str] = []
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        roots.append(
            os.path.join(
                venv,
                f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages",
            )
        )
    roots.extend(site.getsitepackages())
    return roots


def collect_pro_gpu_lib_dirs() -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []
    for root in _site_roots():
        for sub in _LIB_SUBDIRS:
            path = os.path.join(root, sub)
            if os.path.isdir(path) and path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


def ensure_pro_gpu_lib_path() -> str:
    """Prepend Pro GPU library dirs to LD_LIBRARY_PATH; return the updated value."""
    new_dirs = collect_pro_gpu_lib_dirs()
    if not new_dirs:
        return os.environ.get("LD_LIBRARY_PATH", "")

    prefix = os.pathsep.join(new_dirs)
    current = os.environ.get("LD_LIBRARY_PATH", "")
    if current:
        # Avoid duplicating if already applied (e.g. activate hook).
        first = current.split(os.pathsep)[0]
        if first in new_dirs:
            return current
        os.environ["LD_LIBRARY_PATH"] = f"{prefix}{os.pathsep}{current}"
    else:
        os.environ["LD_LIBRARY_PATH"] = prefix
    return os.environ["LD_LIBRARY_PATH"]
