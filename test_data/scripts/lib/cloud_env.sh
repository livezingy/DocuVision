#!/usr/bin/env bash
# Shared cloud path detection for DocuVision acceptance scripts.
# Tencent Cloud Studio (/workspace/DocuVision) and Baidu AI Studio (~/DocuVision).
#
# Optional overrides:
#   DOCUVISION_ROOT  — repo root when not inferred from script location
#   DOCUVISION_CLOUD — force tencent | baidu | generic
#   API_ROOT         — default http://127.0.0.1:8000 (same-node curl on both clouds)

_cloud_env_lib_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}

resolve_repo_root() {
  local candidate lib_dir

  if [[ -n "${DOCUVISION_ROOT:-}" ]]; then
    candidate="$(cd "$DOCUVISION_ROOT" && pwd)"
    if [[ -f "$candidate/backend/run.py" ]]; then
      echo "$candidate"
      return 0
    fi
    echo "FAIL: DOCUVISION_ROOT=$candidate has no backend/run.py" >&2
    return 1
  fi

  if [[ -n "${REPO_ROOT:-}" ]] && [[ -f "${REPO_ROOT}/backend/run.py" ]]; then
    cd "$REPO_ROOT" && pwd
    return 0
  fi

  lib_dir="$(_cloud_env_lib_dir)"
  candidate="$(cd "$lib_dir/../../.." && pwd)"
  if [[ -f "$candidate/backend/run.py" ]]; then
    echo "$candidate"
    return 0
  fi

  echo "FAIL: cannot resolve repo root; set DOCUVISION_ROOT to your clone path" >&2
  return 1
}

detect_cloud_provider() {
  local root="${1:-}"

  if [[ -n "${DOCUVISION_CLOUD:-}" ]]; then
    echo "$DOCUVISION_CLOUD"
    return 0
  fi

  if [[ "${USER:-}" == "aistudio" ]] || [[ -n "${AISTUDIO_PROJECT_ID:-}" ]]; then
    echo "baidu"
    return 0
  fi

  if [[ "$root" == /workspace/* ]] || { [[ -d /workspace ]] && [[ -w /workspace ]]; }; then
    echo "tencent"
    return 0
  fi

  echo "generic"
}

cloud_api_root() {
  echo "${API_ROOT:-http://127.0.0.1:8000}"
}

cloud_ui_hint() {
  local api_root="$1"
  local provider="$2"

  case "$provider" in
    baidu)
      cat <<EOF
Pro UI (Baidu AI Studio): {project_base}/api_serving/8000/frontend/index.html
  Copy {project_base} from the browser URL (segment before /home or /api_serving).
Node API probe (this script): $api_root/api/v1/health
EOF
      ;;
    tencent)
      echo "Pro UI (Tencent Cloud Studio): $api_root/frontend/index.html"
      ;;
    *)
      echo "Pro UI: $api_root/frontend/index.html"
      ;;
  esac
}

cloud_pip_hint() {
  local provider="$1"

  if [[ "$provider" != "baidu" ]]; then
    return 0
  fi

  cat <<'EOF'
Baidu pip note: platform defaults install.user=true — before pip in venv run:
  cat > /tmp/pip-docuvision.conf << 'PIPCONF'
[global]
index-url = http://mirrors.baidubce.com/pypi/simple/
[install]
trusted-host = mirrors.baidubce.com
user = false
PIPCONF
  export PIP_CONFIG_FILE=/tmp/pip-docuvision.conf
See docs/architecture/CLOUD_VALIDATION.md section 1.1
EOF
}

init_cloud_env() {
  REPO_ROOT="$(resolve_repo_root)"
  export REPO_ROOT
  CLOUD_PROVIDER="$(detect_cloud_provider "$REPO_ROOT")"
  export CLOUD_PROVIDER
  API_ROOT="$(cloud_api_root)"
  export API_ROOT
  VENV_ACTIVATE="${VENV_ACTIVATE:-$HOME/docuvision_env/bin/activate}"
  export VENV_ACTIVATE
}
