#!/usr/bin/env bash
# Rebuild DocuVision Pro GPU environment (Cloud Studio / Linux).
#
# Usage:
#   python3 -m venv ~/docuvision_env
#   source ~/docuvision_env/bin/activate
#   cd backend
#   ./install_pro_gpu.sh
#
# Lite CPU backend uses apps/lite/backend/install_deps.sh in docuvision_lite_env — keep separate.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "WARNING: VIRTUAL_ENV is not set. Activate docuvision_env first." >&2
fi

echo "Using: $(command -v python) ($(python -V 2>&1))"

unset LD_LIBRARY_PATH

python -m pip install -U pip

echo "==> Base dependencies (no torch, no paddle)"
python -m pip install -r requirements.txt

echo "==> PyTorch cu124 (KIE)"
python -m pip install -r requirements-gpu-torch.txt

echo "==> PaddlePaddle GPU cu129 (official index only for 3.3.0)"
python -m pip install paddlepaddle-gpu==3.3.0 \
  -i https://www.paddlepaddle.org.cn/packages/stable/cu129/
python -m pip install paddleocr==3.3.2
python -m pip install "paddlex[ocr]==3.3.12"

echo "==> Re-pin NVIDIA CUDA 12.9 libs (+ cuSPARSELt for torch)"
python -m pip install -r requirements-gpu-nvidia.txt

if [[ ! -f .env ]] && [[ -f .env.cloud ]]; then
  cp .env.cloud .env
  echo "Created .env from .env.cloud"
fi

# shellcheck disable=SC1091
source "$ROOT/env_pro_gpu.sh"

python - <<'PY'
import paddle
import torch
import paddlex

print("paddle", paddle.__version__, "cuda", paddle.is_compiled_with_cuda())
print("torch", torch.__version__, "cuda_available", torch.cuda.is_available())
print("paddlex OK")
PY

echo ""
echo "Pro GPU deps OK. Start with:"
echo "  source ~/docuvision_env/bin/activate"
echo "  cd backend && source ./env_pro_gpu.sh"
echo "  DEBUG_MODE=false python run.py"
