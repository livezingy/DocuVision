#!/usr/bin/env bash
# Install DocuVision Lite backend deps into the active virtualenv.
# Usage (Cloud Studio / Linux):
#   python3 -m venv ~/docuvision_lite_env
#   source ~/docuvision_lite_env/bin/activate
#   ./install_deps.sh
#   python -m pytest tests/ -q

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "WARNING: VIRTUAL_ENV is not set. Activate docuvision_lite_env first." >&2
fi

echo "Using: $(command -v python) ($(python -V 2>&1))"
python -m pip install -U pip
python -m pip install -r requirements-lite.txt

python - <<'PY'
from pydantic_settings import BaseSettings
from app.main import app

print("Lite deps OK:", app.title)
PY

echo ""
echo "Run tests with the same Python interpreter:"
echo "  python -m pytest tests/ -q"
