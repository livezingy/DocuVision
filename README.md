# DocuVision

An intelligent document processing system built on [PaddleX](https://github.com/PaddlePaddle/PaddleX) / PP-StructureV3, positioned as an open, self-hostable alternative to **Azure Document Intelligence**–style layout, OCR, tables, and optional enrichment (formulas, seals, key information extraction).

---

## Current status

### What works today

- **FastAPI backend** (`backend/`) exposing REST APIs for document analysis, batch jobs, export, and health checks. Interactive docs: `/docs` when the server is running.
- **Core pipeline** orchestrated around **PP-StructureV3**: layout and region typing, text from `block["content"]` (normalized, no secondary whole-page OCR loop), tables (layout-first strategy with configurable full-page fallback), figures/charts.
- **Coordinate model**: preprocessing keeps **`use_doc_unwarping` disabled** (hard-coded in the engine) so word spacing stays reliable; polygons are mapped back to **original image** space for the `view` layer (`coordinate_space: "original"`).
- **Optional capabilities**: formula recognition (`enable_formula`), seal recognition (`enable_seal`), document-level **KIE** for invoice / ID card / receipt via **PaddleNLP UIE** (`uie-m-base`) behind `enable_kie`, routed by `document_type`.
- **Structured output**: layered **Envelope** (raw / fused / view / quality) with provenance, processing-status fallbacks, and quality metrics aligned with the architecture spec.
- **Debug mode**: service-level `DEBUG_MODE` can persist per-job artifacts under `backend/debug/{job_id}/` and expose `GET /api/v1/jobs/{job_id}/debug` when enabled.
- **Frontend** (`frontend/`): dependency-free static SPA (HTML/CSS/JS) talking to the API; see `frontend/README_FRONTEND.md` for UI details.

### Reference data

- **`test_data/Azure/`**: Azure Layout / DI–style JSON outputs used as a behavioral benchmark (not authoritative for this codebase—implementation details follow `docs/architecture/` and the code).

### Documentation (source of truth)

Authoritative design and contracts live under **`docs/architecture/`**, especially:

| Document | Purpose |
|----------|---------|
| `智能文档处理系统设计方案.md` | System goals, engine choices, envelope layers, API/front-end conventions, phased roadmap |
| `kie.md` | Document-level KIE (UIE), `view.fields` / `quality.kie_*`, tests, optional second engines |
| `main-tracked-issues.md` | Lightweight backlog notes |
| `KIE_TEST_RUN_TRACKER.md` | Cloud KIE validation batches |

---

## Tech stack (typical)

| Layer | Notes |
|-------|--------|
| Runtime | Python **3.10+** (some requirement files mention 3.11 for cloud images) |
| Deep learning | **PaddlePaddle GPU 3.3.x**, **PaddleOCR 3.3.x**, **PaddleX 3.3.x** (see `CLAUDE.md` and `backend/requirements-paddleocr-aistudio.txt`) |
| API | **FastAPI**, **Uvicorn** |
| UI | Static SPA, no Node build step |

Dependency pins and GPU-environment notes are in `backend/requirements-paddleocr-aistudio.txt` and `backend/requirements-colab.txt`. Heavy DL stacks are often preinstalled on target GPU images (e.g. AI Studio); avoid conflicting installs in those environments.

---

## Repository layout

```
DocuVision/
├── backend/           # FastAPI app, orchestrator, PaddleX services, tests
├── frontend/          # Static SPA + README_FRONTEND.md
├── docs/architecture/ # Design specs and trackers (Chinese + technical detail)
├── test_data/         # Sample inputs and Azure reference JSON
└── CLAUDE.md          # Maintainer conventions for this repo
```

---

## Getting started (outline)

1. **Environment**: GPU recommended for production-like latency; CPU may work for smoke tests depending on models loaded.
2. **Python dependencies**: Install from the requirements file that matches your platform (`backend/requirements-paddleocr-aistudio.txt` or `requirements-colab.txt`), respecting preinstalled Paddle versions on managed images.
3. **Configuration**: Use `backend/.env` (you can start from `backend/.env.cloud` where provided). Do not commit secrets.
4. **Run the API** (from `backend/`):

   ```bash
   python run.py
   ```

   Default API base used by the frontend is often `http://localhost:8000/api/v1`—adjust in `frontend/app.js` if needed.
5. **Open the UI**: Serve or open `frontend/index.html` (or rely on static mounting if your deployment bundles frontend with the backend).

For field-level API behavior, response shapes, and debug semantics, rely on **`docs/architecture/智能文档处理系统设计方案.md`** and the running OpenAPI schema.

---

## Testing

Examples called out in architecture notes:

```bash
pytest backend/tests/test_kie_service.py backend/tests/test_orchestrator_order.py
```

Additional tests live under `backend/tests/` (e.g. table strategy, formula grading).

---

## Roadmap (high level)

Aligned with **Phase 3** in the architecture document—**document-level KIE with UIE is already integrated**; remaining themes include:

| Theme | Direction |
|-------|-----------|
| **Second KIE engine (optional)** | Evaluate models such as **Qwen2.5-VL**, **PP-ChatOCRv4-doc**, or **`uie-x-base`** while keeping **`view.fields` / `quality.kie_*`** stable or versioned |
| **kie_confidence_source** | Today tied to `uie-m-base` in the orchestrator; should become configuration-driven when multiple engines exist |
| **Long-document Q&A** | PaddleOCR-VL–style scenarios |
| **Translation** | PP-DocTranslation for multilingual output |
| **Retrieval** | Vector indexing over processed content |

See **`docs/architecture/智能文档处理系统设计方案.md`** §10 for the full phased checklist and **`docs/architecture/kie.md`** §8 for KIE-specific follow-ups.

---

## Contributing

- Follow existing code layout and the contracts in `docs/architecture/`.
- Prefer small, focused changes with tests where behavior is specified.
- Keep secrets and tokens out of the repository and logs.

---

## License

No `LICENSE` file is present in the repository root yet; clarify terms before redistribution.
