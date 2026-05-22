#!/usr/bin/env python
"""DocuVision Lite backend launcher."""

import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    print(
        f"""
    ╔══════════════════════════════════════════════════════╗
    ║     DocuVision Lite — CPU Table & OCR API            ║
    ║     API docs: http://{settings.HOST}:{settings.PORT}/docs
    ╚══════════════════════════════════════════════════════╝
    """
    )
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
