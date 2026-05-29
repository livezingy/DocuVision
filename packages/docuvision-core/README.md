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

Weights live in **`models/`** next to source (not in Git). Full host-migration guide: **[models/README.md](models/README.md)**.

| Directory | Used by |
|-----------|---------|
| `models/table-transformer/detection/` | Table Transformer detection |
| `models/table-transformer/structure/` | Table Transformer structure |
| `models/EasyOCR/model/` | EasyOCR weights |

Bootstrap once: `bash scripts/bootstrap_lite_models.sh` from this package root.

See [apps/lite/backend/README.md](../../apps/lite/backend/README.md) for Lite run instructions and Tesseract apt packages.
