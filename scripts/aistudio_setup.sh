#!/usr/bin/env bash
# Baidu AI Studio environment setup for DocuVision.
#
# Why this file exists:
#   AI Studio resets ~/.bashrc and the home root (~/.paddlex, pip system dirs)
#   on every restart; only /home/aistudio/work (personal workspace, 100G) and
#   the project space (e.g. ~/DocuVision) are persistent
#   (see https://ai.baidu.com/ai-doc/AISTUDIO/5k39vd65f Q7/Q11 and
#        https://ai.baidu.com/ai-doc/AISTUDIO/sk3e2z8sb).
# So environment variables and the PaddleX model cache MUST live under a
# persistent path. Source this script once per fresh terminal before running
# the backend:
#
#     source ~/DocuVision/scripts/aistudio_setup.sh
#
# PaddleX model cache (official env var, see paddlex/utils/cache.py:
#   CACHE_DIR = os.environ.get("PADDLE_PDX_CACHE_HOME", "~/.paddlex"))
# Point it at the persistent work dir so downloaded models survive restarts.
export PADDLE_PDX_CACHE_HOME=/home/aistudio/work/paddlex_cache

# PPStructureV3 worker init timeout: first load still needs to read models
# from disk into GPU; 600s is a safe ceiling. Tunable via env if needed.
export APP_LAYOUT_WORKER_INIT_TIMEOUT=600

# Skip PaddleX model-host connectivity checks (AI Studio proxy to HF is flaky).
export DISABLE_MODEL_SOURCE_CHECK=True
export PADDLEX_DISABLE_MODEL_SOURCE_CHECK=True
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

echo "[aistudio_setup] PADDLE_PDX_CACHE_HOME=$PADDLE_PDX_CACHE_HOME"
echo "[aistudio_setup] APP_LAYOUT_WORKER_INIT_TIMEOUT=$APP_LAYOUT_WORKER_INIT_TIMEOUT"
