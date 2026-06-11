# DocuVision Lite Backend

CPU-friendly table extraction and OCR API (`/api/v1/lite`).

## Run locally

> **zsh**: quote the editable install path so `[lite,dev]` is not glob-expanded.

```bash
cd apps/lite/backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-lite.txt
pip install -e '../../../packages/docuvision-core[lite,dev]'
python run_lite.py
```

- API docs: http://127.0.0.1:8001/docs  
- UI: http://127.0.0.1:8001/lite/lite.html  

## Optional: Tesseract + Table Transformer (image tables)

Baseline `requirements-lite.txt` installs **`docuvision-core[lite]`**, which includes:

| Component | In `[lite]` pip extra? | Notes |
|-----------|------------------------|-------|
| `pytesseract` | Yes | Python wrapper only |
| `easyocr` | Yes | Downloads weights on first use |
| **Tesseract binary** | **No** | Install via OS package manager |
| **transformers / torch** | **No** | Install `[ocr-heavy]` extra |
| **matplotlib** | **No** | Install `[ocr-heavy]` (TableParser debug viz) |

### Cloud Studio / Linux (recommended)

```bash
# System binaries (not pip)
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng ghostscript

cd apps/lite/backend
source ~/docuvision_lite_env/bin/activate
pip install -r requirements-lite.txt
pip install -r requirements-lite-ocr-heavy.txt
# equivalent: pip install -e '../../../packages/docuvision-core[ocr-heavy]'
```

Verify Tesseract:

```bash
which tesseract
tesseract --version
```

### Model and data paths

All ML weights default to **`packages/docuvision-core/models/`** (same directory as source via `get_app_dir()`).  
See **[models/README.md](../../../packages/docuvision-core/models/README.md)** for host migration and offline scenarios.

**One-time bootstrap** (after pip install):

```bash
cd packages/docuvision-core
bash scripts/bootstrap_lite_models.sh
python scripts/bootstrap_lite_models.py --status-only
```

| Purpose | Default path | If missing |
|---------|--------------|------------|
| Table Transformer **detection** | `models/table-transformer/detection/` | Bootstrap or first-run Hub download **into this directory** |
| Table Transformer **structure** | `models/table-transformer/structure/` | Same |
| **EasyOCR** weights | `models/EasyOCR/model/` | Bootstrap or first EasyOCR run |
| **Tesseract binary** | `PATH` (`tesseract` on Linux) | Install via apt; Windows: optional `tesseract/tesseract.exe` |
| **Tesseract languages** | Linux: `/usr/share/tesseract-ocr/*/tessdata` | `tesseract-ocr-eng` via apt |

Optional: `DOCUVISION_MODELS_DIR` overrides the models root; `DOCUVISION_OFFLINE=1` disables Hub fallback.

### UI engines (Analysis Options)

- **Text + Tesseract**: needs system `tesseract` on `PATH`.
- **Text + EasyOCR**: included in `[lite]`; weights under `models/EasyOCR/model/`.
- **Raster documents (image / scan PDF)**: **text OCR only** (EasyOCR or Tesseract). Table Transformer for photos/scans is **disabled by default** (`RASTER_TABLE_EXTRACTION_ENABLED=false`).
- **Digital PDF tables**: pdfplumber / camelot (unchanged).
- To re-enable raster Transformer (dev only): set env `RASTER_TABLE_EXTRACTION_ENABLED=true` and install `[ocr-heavy]`.

## Local reference docs (PDFDataExtractor)

PDFDataExtractor reference documents are kept **locally only** under `apps/lite/backend/docs/`. This directory is listed in `.gitignore` and is not pushed to the DocuVision remote.

One-time sync from a local PDFDataExtractor checkout:

```bash
# Linux / macOS
mkdir -p apps/lite/backend/docs
cp -r ../PDFDataExtractor/docs/* apps/lite/backend/docs/
```

```powershell
# Windows (adjust source path as needed)
mkdir apps\lite\backend\docs
xcopy /E /I d:\3_PROJECTS\PDFDataExtractor\docs apps\lite\backend\docs
```

Verify the folder is ignored:

```bash
git check-ignore -v apps/lite/backend/docs/
git ls-files apps/lite/backend/docs/   # should print nothing
```


## Tests

See [tests/README.md](tests/README.md) for CI and cloud validation steps.
