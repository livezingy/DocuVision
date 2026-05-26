#!/usr/bin/env python
"""
DocuVision 启动脚本
"""

# CRITICAL: Set environment variables FIRST, before importing ANY modules
# This must be at the very top, even before importing os
import os
import shutil

# CRITICAL: 禁用 oneDNN (MKL-DNN) 优化以避免 PaddlePaddle 3.x 兼容性问题
# 解决错误: ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]
# 这些环境变量必须在导入任何 PaddlePaddle 模块之前设置
os.environ['FLAGS_use_mkldnn'] = '0'  # 改为 '0' 而不是 'False'
os.environ['FLAGS_onednn'] = '0'
os.environ['MKLDNN_ENABLED'] = '0'
os.environ['FLAGS_use_onednn'] = '0'  # 添加额外的标志
os.environ['PADDLE_USE_ONEDNN'] = '0'  # PaddlePaddle 3.x 可能需要这个

# Disable PaddleX model source host connectivity checks as early as possible.
# Keep multiple env keys for compatibility across PaddleX revisions.
os.environ['DISABLE_MODEL_SOURCE_CHECK'] = 'True'
os.environ['PADDLEX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

from app.core.gpu_lib_path import ensure_pro_gpu_lib_path

ensure_pro_gpu_lib_path()


def _ensure_env_from_cloud_template() -> None:
    """Create backend/.env from backend/.env.cloud when .env is missing."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, ".env")
    env_cloud_path = os.path.join(current_dir, ".env.cloud")
    if os.path.exists(env_path):
        return
    if not os.path.exists(env_cloud_path):
        return
    try:
        shutil.copyfile(env_cloud_path, env_path)
        print(f"[Startup] Created .env from template: {env_cloud_path}")
    except Exception as exc:
        print(f"[Startup] Failed to copy .env.cloud -> .env: {exc}")


_ensure_env_from_cloud_template()

import uvicorn
from app.core.config import settings


if __name__ == "__main__":
    print(f"""
    ╔══════════════════════════════════════════════════════╗
    ║                                                      ║
    ║     📄 DocuVision - 智能文档处理系统                 ║
    ║                                                      ║
    ║     启动中...                                        ║
    ║     API 文档: http://{settings.HOST}:{settings.PORT}/docs          ║
    ║                                                      ║
    ╚══════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )

