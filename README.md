# DocuVision

DocuVision is an intelligent document processing stack built on [PaddleX](https://github.com/PaddlePaddle/PaddleX) and PP-StructureV3. It targets a **self-hosted**, **Azure Document Intelligence–style** workflow: layout and OCR, tables and figures, optional formulas and seals, and optional document-level **KIE** (key information extraction) when enabled.

---

## UI overview

The web UI is a static single-page app under `frontend/` (no Node build). Layout matches `frontend/index.html` and `frontend/README_FRONTEND.md`.

- **Top navigation**: primary **Document Processing** tab; **Batch Processing** is a disabled placeholder. **Settings** is disabled; **Help** opens API / help documentation (configurable URL, default `/docs`).
- **Left panel**: **Upload Document** (drag-and-drop or file picker for PDF, PNG, JPG, TIFF) and **Processing Queue** listing jobs in flight.
- **Center panel**: **document preview** with pagination, **Run Analysis**, and **Analysis Options** (modal) for pipeline toggles.
- **Right panel**: **Processing Results** with main tabs **Content** and **Result**. Content exposes sub-tabs (e.g. Text, Tables, Figures, and optional Fields / Formulas / Seals when the backend returns them). **Result** shows JSON with copy/download. **Export Results** offers structured export actions.
- **Footer (status bar)**: connection / readiness, **stack version** and **KIE ready/cold** driven by `GET /health`, plus **API version** from the same payload.

### Screenshot

![DocuVision UI](docs/architecture/media/docuvision-ui.png)

Replace the placeholder image with a real capture; see `docs/architecture/media/README.md`.

---

## Live demo

<!-- Maintainer: replace with a hosted demo URL when available. -->

[Live demo](https://example.com) — link is a placeholder until a public deployment is published.

---

## Architecture and capabilities (summary)

- **Backend**: FastAPI app under `backend/`, orchestrating PaddleX PP-StructureV3 and optional cloud **KIE** via **Qwen2.5-VL** (see `docs/architecture/kie.md`).
- **APIs**: legacy task-style endpoints under `POST /api/v1/...` (e.g. analyze, jobs, export) coexist with Phase-1 style `documents:analyze` and job polling; authoritative shapes and evolution are described in `docs/architecture/` (start with `智能文档处理系统设计方案.md`).
- **Response model**: layered **Envelope** (`raw` / `fused` / `view` / `quality`) with provenance and quality hints aligned to the architecture spec.
- **Health**: `GET /health` reports dependency versions, API revision, and KIE warmup state for the footer and operations.

For KIE field layout, `view.fields`, and `quality.kie_*`, use **`docs/architecture/kie.md`**. For phased roadmap and API conventions, use the main architecture document in the same folder.

---

## Reference data

Under **`test_data/`** (tracked): **`Azure/`** holds reference JSON in an Azure Layout / DI–like shape; **`testfiles/`** holds fixed samples; **`acceptance/`** holds acceptance matrices and notes. **`TestResult/`** is for local or CI scratch output only (ignored by Git).

---

## Tech stack (typical)

| Layer        | Notes |
| ------------ | ----- |
| Runtime      | Python **3.10+** (see `backend/requirements.txt` for image / CUDA notes) |
| Deep learning | **PaddlePaddle GPU 3.3.x**, **PaddleOCR 3.3.x**, **PaddleX 3.3.x** |
| API          | **FastAPI**, **Uvicorn** |
| UI           | Static SPA, no Node build step |

Pins live in **`backend/requirements.txt`** (single source for Python deps in this repo).

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

For response shapes and debug semantics, use **`docs/architecture/智能文档处理系统设计方案.md`** and the live OpenAPI schema at `/docs`.

---

## Testing

Examples referenced in architecture notes:

```bash
pytest backend/tests/test_kie_service.py backend/tests/test_kie_return_raw_contract.py backend/tests/test_orchestrator_order.py
```

More tests live under `backend/tests/`. Document-type acceptance: `test_data/acceptance/doc_types.md`.

---

## Roadmap (high level)

Aligned with **Phase 3+** in the architecture document (document-level KIE on **Qwen2.5-VL** today). Further themes:

| Theme | Direction |
| ----- | --------- |
| **Second KIE engine (optional)** | Evaluate models such as **PP-ChatOCRv4-doc** or **`uie-x-base`** while keeping **`view.fields` / `quality.kie_*`** stable or versioned |
| **kie_confidence_source** | Keep configuration-driven when multiple engines exist |
| **Long-document Q&A** | PaddleOCR-VL–style scenarios |
| **Translation** | e.g. PP-DocTranslation for multilingual output |
| **Retrieval** | Vector indexing over processed content |

See **`docs/architecture/智能文档处理系统设计方案.md`** §10 for the full phased checklist and **`docs/architecture/kie.md`** for KIE specifics.

---

## Contributing

- Follow the contracts in `docs/architecture/` and existing module layout.
- Prefer small, focused changes with tests where behavior is specified.
- Keep secrets and tokens out of the repository and logs.

---

## License

No `LICENSE` file is present in the repository root yet; clarify terms before redistribution.
