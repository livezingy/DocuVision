#!/usr/bin/env bash
# Download Lite model weights into packages/docuvision-core/models/ (source-adjacent storage).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODELS_ROOT="${DOCUVISION_MODELS_DIR:-${CORE_ROOT}/models}"

cd "${CORE_ROOT}"

echo "Models root: ${MODELS_ROOT}"
mkdir -p "${MODELS_ROOT}/table-transformer/detection"
mkdir -p "${MODELS_ROOT}/table-transformer/structure"
mkdir -p "${MODELS_ROOT}/EasyOCR/model"

if ! command -v huggingface-cli >/dev/null 2>&1; then
  echo "Installing huggingface_hub for huggingface-cli..."
  pip install -q huggingface_hub
fi

echo "Downloading Table Transformer detection model..."
huggingface-cli download microsoft/table-transformer-detection \
  --local-dir "${MODELS_ROOT}/table-transformer/detection"

echo "Downloading Table Transformer structure model..."
huggingface-cli download microsoft/table-transformer-structure-recognition \
  --local-dir "${MODELS_ROOT}/table-transformer/structure"

echo "Downloading EasyOCR English weights..."
python "${SCRIPT_DIR}/bootstrap_lite_models.py" --easyocr-only

echo ""
echo "Model bootstrap complete. Summary:"
python "${SCRIPT_DIR}/bootstrap_lite_models.py" --status-only
