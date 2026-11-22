#!/usr/bin/env bash
# AI Studio 终端自举：让新开的默认终端自动激活 docuvision_env 并进入仓库目录。
#
# 背景：AI Studio 重启环境后 ~/.bashrc 被重置（仅 /home/aistudio/work 持久化），
# 所以每次环境重启/重建后，在任一终端跑一次本脚本即可，之后新开的终端自动：
#   1) source ~/docuvision_env/bin/activate
#   2) cd ~/work/DocuVision
#
# 用法（在仓库内任一路径执行，幂等可重复）：
#   bash scripts/cloud/aistudio_term_init.sh
#
# 路径可用环境变量覆盖：DOCUVISION_VENV / DOCUVISION_ROOT。
# venv 缺失时不会写 .bashrc —— 先按 CLOUD_VALIDATION.md §1.1 重建 venv。

set -euo pipefail

VENV="${DOCUVISION_VENV:-$HOME/docuvision_env}"
REPO="${DOCUVISION_ROOT:-$HOME/work/DocuVision}"
MARKER="# docuvision-pro-term-init (idempotent block, do not edit below)"

if [[ ! -f "$VENV/bin/activate" ]]; then
  echo "ERROR: venv not found: $VENV/bin/activate" >&2
  echo "       rebuild first per docs/architecture/CLOUD_VALIDATION.md §1.1" >&2
  exit 1
fi
if [[ ! -d "$REPO/backend" ]]; then
  echo "ERROR: repo not found: $REPO (need backend/ inside)" >&2
  exit 1
fi

touch "$HOME/.bashrc"
if grep -qF "$MARKER" "$HOME/.bashrc"; then
  echo "OK: .bashrc already configured (marker found) — nothing to do"
else
  cat >> "$HOME/.bashrc" <<EOF

$MARKER
# auto: activate docuvision_env + cd repo (AI Studio terminal bootstrap)
if [ -f "$VENV/bin/activate" ]; then
  . "$VENV/bin/activate"
fi
if [ -d "$REPO" ]; then
  cd "$REPO"
fi
EOF
  echo "OK: injected into $HOME/.bashrc — takes effect in NEWLY opened terminals"
fi

# 当前终端也立即生效
# shellcheck disable=SC1091
. "$VENV/bin/activate"
cd "$REPO"
echo "current shell now: VIRTUAL_ENV=${VIRTUAL_ENV:-<unset>} pwd=$(pwd)"
