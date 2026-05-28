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
