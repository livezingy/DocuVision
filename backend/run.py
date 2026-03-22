#!/usr/bin/env python
"""
DocuVision 启动脚本
"""

# CRITICAL: Set environment variables FIRST, before importing ANY modules
# This must be at the very top, even before importing os
import os

# CRITICAL: 禁用 oneDNN (MKL-DNN) 优化以避免 PaddlePaddle 3.x 兼容性问题
# 解决错误: ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]
# 这些环境变量必须在导入任何 PaddlePaddle 模块之前设置
os.environ['FLAGS_use_mkldnn'] = '0'  # 改为 '0' 而不是 'False'
os.environ['FLAGS_onednn'] = '0'
os.environ['MKLDNN_ENABLED'] = '0'
os.environ['FLAGS_use_onednn'] = '0'  # 添加额外的标志
os.environ['PADDLE_USE_ONEDNN'] = '0'  # PaddlePaddle 3.x 可能需要这个

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

