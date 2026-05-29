# DocuVision Core

Shared table extraction and OCR engines for DocuVision Lite and Pro.

## Install extras

```bash
pip install -e ".[lite]"        # PDF tables, EasyOCR, pytesseract wrapper
pip install -e ".[ocr-heavy]"   # Table Transformer (torch, transformers, matplotlib)
pip install -e ".[dev]"         # pytest
```

**Tesseract OCR binary** is not a pip dependency. On Linux install `tesseract-ocr` via apt; Lite README documents paths.

## Model directories (under package root)

| Directory | Used by |
|-----------|---------|
| `models/table-transformer/detection/` | Table Transformer detection (local or HF fallback) |
| `models/table-transformer/structure/` | Table Transformer structure (local or HF fallback) |
| `models/EasyOCR/` | EasyOCR weights (auto-download) |

See [apps/lite/backend/README.md](../../apps/lite/backend/README.md) for Hugging Face offline download commands.
