#!/usr/bin/env bash
# Append pip-shipped NVIDIA / PyTorch shared libraries for Pro GPU runtime.
#
# Applied automatically when docuvision_env is activated (see install_pro_gpu.sh).
# Also invoked from run.py / app.main / pytest conftest — manual source is optional.
#
#   source ./env_pro_gpu.sh   # only if venv hook was not installed

_pro_gpu_lib_dirs() {
  python - <<'PY'
import os
import site
import sys

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

subs = [
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
]
seen: set[str] = set()
paths: list[str] = []
for root in roots:
    for sub in subs:
        path = os.path.join(root, sub)
        if os.path.isdir(path) and path not in seen:
            seen.add(path)
            paths.append(path)
print(":".join(paths))
PY
}

_paths="$(_pro_gpu_lib_dirs)"
if [[ -n "${_paths}" ]]; then
  export LD_LIBRARY_PATH="${_paths}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
fi
unset -f _pro_gpu_lib_dirs
