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

All paths below are under **`packages/docuvision-core/`** (package root from `get_app_dir()`).

| Purpose | Default path | If missing |
|---------|--------------|------------|
| Table Transformer **detection** | `models/table-transformer/detection/` | Auto-download from Hugging Face `microsoft/table-transformer-detection` |
| Table Transformer **structure** | `models/table-transformer/structure/` | Auto-download from Hugging Face `microsoft/table-transformer-structure-recognition` |
| **EasyOCR** weights | `models/EasyOCR/` | Auto-download on first EasyOCR run |
| **Tesseract binary** | `PATH` (`tesseract` on Linux) | Required for Text OCR when Tesseract is selected; Windows bundle: `tesseract/tesseract.exe` under package root |
| **Tesseract languages** | Linux: `/usr/share/tesseract-ocr/*/tessdata` | Install `tesseract-ocr-eng` (or locale packages) via apt |

**Optional offline Transformer weights** (avoid HF Hub on first run):

```bash
cd packages/docuvision-core
pip install huggingface_hub
huggingface-cli download microsoft/table-transformer-detection --local-dir models/table-transformer/detection
huggingface-cli download microsoft/table-transformer-structure-recognition --local-dir models/table-transformer/structure
```

Large model files are **not** committed to Git. First run may download ~100MB+ from Hugging Face (set `HF_TOKEN` for higher rate limits).

### UI engines (Analysis Options)

- **Text + Tesseract**: needs system `tesseract` on `PATH`.
- **Tables + Transformer**: needs `pip install -e '...docuvision-core[ocr-heavy]'` (torch + transformers + matplotlib).
- Transformer table extraction can still use EasyOCR internally for cell text when cell OCR fails; that is separate from the Text (OCR) engine selection.

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

Maintain the canonical docs in the **PDFDataExtractor** repository; this copy is for Lite development reference only.

## Tests

See [tests/README.md](tests/README.md) for CI and cloud validation steps.
