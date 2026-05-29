# DocuVision Lite Model Storage

All Lite ML weights live under **`packages/docuvision-core/models/`** by default (next to source).  
Override with environment variable **`DOCUVISION_MODELS_DIR`** when models must live on a shared mount.

**Weights are not committed to Git.** Only this README and `.gitkeep` placeholders are versioned.

## Directory layout

| Path | Component | Notes |
|------|-----------|--------|
| `table-transformer/detection/` | Table Transformer detection | Hugging Face `microsoft/table-transformer-detection` |
| `table-transformer/structure/` | Table Transformer structure | Hugging Face `microsoft/table-transformer-structure-recognition` |
| `EasyOCR/model/` | EasyOCR CRAFT + recognition | `craft_mlt_25k.pth`, `english_g2.pth`, etc. |

**Tesseract** (Text OCR binary and language packs) is **not** stored here on Linux — install via apt (`tesseract-ocr`, `tesseract-ocr-eng`). On Windows you may bundle `tesseract/` under the package root instead.

**Pro-only caches** (PaddleOCR under `~/.paddlex/`, KIE ModelScope) are outside this tree; Lite does not use them.

## First-time setup (bootstrap)

From `packages/docuvision-core/` after `pip install -e '.[lite,ocr-heavy]'`:

```bash
# Linux / Cloud Studio
bash scripts/bootstrap_lite_models.sh

# Windows (EasyOCR + status; run huggingface-cli manually for Transformer)
python scripts/bootstrap_lite_models.py --easyocr-only
huggingface-cli download microsoft/table-transformer-detection --local-dir models/table-transformer/detection
huggingface-cli download microsoft/table-transformer-structure-recognition --local-dir models/table-transformer/structure
```

Verify:

```bash
python scripts/bootstrap_lite_models.py --status-only
```

Runtime also downloads missing Transformer weights on first use and **writes them into this directory** (not only `~/.cache/huggingface`).

## Changing runtime host — what to do

| Scenario | Action | Result |
|----------|--------|--------|
| **A. Same persistent disk, restart only** | Nothing | `models/` remains on disk; loads with `local_files_only` |
| **B. New host, repo + `models/` on same volume** | `git pull` or rsync `packages/docuvision-core/` including `models/` | No bootstrap |
| **C. New host, clone source only (`models/` empty)** | `pip install` then run **`bootstrap_lite_models.sh` once** | Weights download next to source |
| **D. Shared model mount (optional)** | Set `DOCUVISION_MODELS_DIR=/path/to/shared/models` | All hosts use same weights; source tree can omit `models/` |
| **E. Offline / air-gapped** | Copy entire `models/` from a prepared machine | Set `DOCUVISION_OFFLINE=1` to forbid Hub fallback |

### Recommended migration (B or manual copy)

```bash
# On old host (archive)
tar -czf docuvision-models.tgz -C packages/docuvision-core models

# On new host (after clone + pip install)
tar -xzf docuvision-models.tgz -C packages/docuvision-core
python scripts/bootstrap_lite_models.py --status-only
```

If the whole project directory sits on a cloud persistent volume, **`models/` moves with the volume** — no extra configuration.

### What must not go to GitHub

- Any file under `models/` except `README.md` and `.gitkeep`
- Hugging Face caches in `~/.cache/huggingface` (optional; not the primary store)

## Environment variables

| Variable | Purpose |
|----------|---------|
| `DOCUVISION_MODELS_DIR` | Override default `get_app_dir()/models` |
| `DOCUVISION_OFFLINE=1` | Fail if local weights missing; do not download from Hub |
| `HF_TOKEN` | Optional; higher Hugging Face rate limits during bootstrap |

## Related docs

- [apps/lite/backend/README.md](../../../apps/lite/backend/README.md) — Lite run + apt packages
- [docuvision-core README](../README.md) — pip extras
