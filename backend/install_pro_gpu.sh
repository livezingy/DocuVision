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

echo "==> Install venv activate hook (auto LD_LIBRARY_PATH on activate)"
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  mkdir -p "${VIRTUAL_ENV}/bin/activate.d"
  cp "$ROOT/env_pro_gpu.sh" "${VIRTUAL_ENV}/bin/docuvision_pro_gpu_env.sh"
  cat > "${VIRTUAL_ENV}/bin/activate.d/docuvision_pro_gpu.sh" <<'EOF'
# DocuVision Pro GPU — auto LD_LIBRARY_PATH when docuvision_env activates
if [[ -n "${VIRTUAL_ENV:-}" && -f "${VIRTUAL_ENV}/bin/docuvision_pro_gpu_env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${VIRTUAL_ENV}/bin/docuvision_pro_gpu_env.sh"
fi
EOF
  echo "Installed ${VIRTUAL_ENV}/bin/activate.d/docuvision_pro_gpu.sh"
fi

if [[ ! -f .env ]] && [[ -f .env.cloud ]]; then
  cp .env.cloud .env
  echo "Created .env from .env.cloud"
fi

# shellcheck disable=SC1091
source "$ROOT/env_pro_gpu.sh"

python - <<'PY'
import paddle
import torch
import torchvision
import paddlex

print("paddle", paddle.__version__, "cuda", paddle.is_compiled_with_cuda())
print("torch", torch.__version__, "cuda_available", torch.cuda.is_available())
print("torchvision", torchvision.__version__)
print("paddlex OK")
PY

echo ""
echo "Pro GPU deps OK. LD_LIBRARY_PATH is set when you:"
echo "  1) source ~/docuvision_env/bin/activate  (venv activate.d hook)"
echo "  2) python run.py / pytest                 (auto in run.py & conftest)"
echo ""
echo "Start server:"
echo "  source ~/docuvision_env/bin/activate"
echo "  cd backend && DEBUG_MODE=false python run.py"
