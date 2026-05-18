# DocuVision

DocuVision is an intelligent document processing stack built on [PaddleX](https://github.com/PaddlePaddle/PaddleX) and Qwen2.5-VL. It targets a **self-hosted**, **Azure Document Intelligence–style** workflow: layout and OCR, tables and figures, optional formulas and seals, and optional document-level **KIE** (key information extraction) when enabled.

---

## UI overview

![DocuVision UI](docs/architecture/media/docuvision-ui.png)

The web UI is a static single-page app under `frontend/` (no Node build). Layout matches `frontend/index.html` and `frontend/README_FRONTEND.md`.

- **Top navigation**: primary **Document Processing** tab; **Batch Processing** is a disabled placeholder. **Settings** is disabled; **Help** opens API / help documentation (configurable URL, default `/docs`).
- **Left panel**: **Upload Document** (drag-and-drop or file picker for PDF, PNG, JPG, TIFF) and **Processing Queue** listing jobs in flight.
- **Center panel**: **document preview** with pagination, **Run Analysis**, and **Analysis Options** (modal) for pipeline toggles.
- **Right panel**: **Processing Results** with main tabs **Content** and **Result**. Content exposes sub-tabs (e.g. Text, Tables, Figures, and optional Fields / Formulas / Seals when the backend returns them). **Result** shows JSON with copy/download. **Export Results** offers structured export actions.
- **Footer (status bar)**: connection / readiness, **stack version** and **KIE ready/cold** driven by `GET /health`, plus **API version** from the same payload.

### Examples

![DocuVision process image with table](docs/architecture/media/DocVision_table.gif)

![DocuVision process receipt](docs/architecture/media/DocVision_receipt.gif)

![DocuVision process invoice](docs/architecture/media/DocVision_Invoice.gif)
---

## Repository layout

```
DocuVision/
├── backend/           # FastAPI app, orchestrator, PaddleX services, tests
├── frontend/          # Static SPA + README_FRONTEND.md
├── docs/architecture/ # Design specs and trackers
└── test_data/         # acceptance, testfiles, Azure refs; TestResult excluded
```

---

## Getting started (outline)

1. **Environment**: GPU recommended for production-like latency; CPU may suffice for smoke tests depending on models.
2. **Python dependencies**: `cd backend && pip install -r requirements.txt` — follow the header comments for Paddle / torch vs. preinstalled images.
3. **Configuration**: use `backend/.env` (you may copy from `backend/.env.cloud` where provided). Do not commit secrets.
4. **Run the API** (from `backend/`):

   ```bash
   python run.py
   ```

   The frontend defaults to `http://localhost:8000/api/v1`; adjust `frontend/app.js` if needed.
5. **Open the UI**: open or serve `frontend/index.html`.

---


## License

No `LICENSE` file is present in the repository root yet; clarify terms before redistribution.
